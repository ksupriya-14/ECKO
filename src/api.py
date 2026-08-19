"""
FastAPI Web Interface for Micro-Entrepreneur Performance Worker

Provides REST API endpoints and web interface for:
- CSV file upload
- Automatic worker execution
- Automatic verification
- Results retrieval
"""
import sys
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from worker import run_worker, WorkerError
from verify import verify

# Initialize FastAPI app
app = FastAPI(
    title="Micro-Entrepreneur Performance Worker API",
    description="AI Worker for partner performance classification and escalation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("api_outputs")
LOGS_DIR = Path("api_logs")
STATIC_DIR = Path(__file__).parent.parent / "static"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Pydantic models for API responses
class WorkerResponse(BaseModel):
    success: bool
    message: str
    run_id: str
    timestamp: str
    input_file: str
    output_files: Dict[str, str]
    summary: Dict[str, Any]
    verification: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    success: bool
    message: str
    error: str
    timestamp: str


def cleanup_run_files(run_id: str):
    """Clean up temporary files for a specific run"""
    try:
        # Clean up uploaded file
        upload_file = UPLOAD_DIR / f"{run_id}.csv"
        if upload_file.exists():
            upload_file.unlink()
        
        # Clean up output directories
        output_path = OUTPUT_DIR / run_id
        if output_path.exists():
            shutil.rmtree(output_path)
        
        log_path = LOGS_DIR / run_id
        if log_path.exists():
            shutil.rmtree(log_path)
    except Exception as e:
        print(f"Error cleaning up files for run {run_id}: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Micro-Entrepreneur Performance Worker API",
        "version": "1.0.0",
        "endpoints": {
            "POST /upload": "Upload CSV file for processing",
            "GET /status/{run_id}": "Check processing status",
            "GET /results/{run_id}": "Get processing results",
            "GET /download/{run_id}/{file_type}": "Download output files",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Micro-Entrepreneur Performance Worker API"
    }


@app.post("/upload", response_model=WorkerResponse)
async def upload_and_process(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with partner data")
):
    """
    Upload CSV file and automatically run worker + verification
    
    - **file**: CSV file with partner activity data
    - Returns: Processing results with verification status
    """
    # Generate unique run ID
    run_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
        # Save uploaded file
        upload_path = UPLOAD_DIR / f"{run_id}.csv"
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create run-specific directories
        run_output_dir = OUTPUT_DIR / run_id
        run_log_dir = LOGS_DIR / run_id
        run_output_dir.mkdir(exist_ok=True)
        run_log_dir.mkdir(exist_ok=True)
        
        # Run the worker
        try:
            out_df, val_result, audit = run_worker(
                input_path=str(upload_path),
                outdir=str(run_output_dir),
                logdir=str(run_log_dir)
            )
            
            # Run verification
            try:
                checks = verify(
                    input_path=str(upload_path),
                    outdir=str(run_output_dir),
                    logdir=str(run_log_dir)
                )
                verification_passed = all(c.passed for c in checks)
                verification_results = {
                    "passed": verification_passed,
                    "total_checks": len(checks),
                    "passed_checks": sum(1 for c in checks if c.passed),
                    "failed_checks": sum(1 for c in checks if not c.passed),
                    "details": [
                        {"name": c.name, "passed": c.passed, "detail": c.detail}
                        for c in checks
                    ]
                }
            except Exception as e:
                verification_passed = False
                verification_results = {
                    "passed": False,
                    "error": str(e),
                    "details": []
                }
            
            # Load summary report
            summary_path = run_output_dir / "summary_report.md"
            if summary_path.exists():
                with open(summary_path, "r") as f:
                    summary_content = f.read()
            else:
                summary_content = "Summary report not generated"
            
            # Load classification results for summary
            classification_df = pd.read_csv(run_output_dir / "partner_classification_output.csv")
            review_queue_df = pd.read_csv(run_output_dir / "human_review_queue.csv")
            
            # Build escalated partners list for the dashboard
            escalated_partners = []
            for _, row in review_queue_df.iterrows():
                escalated_partners.append({
                    "partner_id": row.get("partner_id"),
                    "partner_name": row.get("partner_name", ""),
                    "classification": row.get("classification", ""),
                    "reasoning": row.get("reasoning", ""),
                })
            
            # Build summary
            summary = {
                "total_partners": len(classification_df),
                "escalated_count": int(classification_df['escalate'].sum()),
                "classification_breakdown": classification_df['classification'].value_counts().to_dict(),
                "escalated_partners": escalated_partners,
                "summary_report": summary_content
            }
            
            # Build output file paths
            output_files = {
                "classification": f"/download/{run_id}/classification",
                "review_queue": f"/download/{run_id}/review_queue",
                "summary_report": f"/download/{run_id}/summary_report",
                "validation_report": f"/download/{run_id}/validation_report",
                "audit_log": f"/download/{run_id}/audit_log"
            }
            
            return WorkerResponse(
                success=True,
                message="File processed successfully",
                run_id=run_id,
                timestamp=timestamp,
                input_file=file.filename,
                output_files=output_files,
                summary=summary,
                verification=verification_results
            )
            
        except WorkerError as e:
            # Worker validation/data error — return meaningful error to client
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            # Worker execution failed unexpectedly
            raise HTTPException(status_code=500, detail=f"Worker execution failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        # General error
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/download/{run_id}/{file_type}")
async def download_file(run_id: str, file_type: str):
    """
    Download output files from a specific run
    
    - **run_id**: Unique identifier for the processing run
    - **file_type**: Type of file to download (classification, review_queue, summary_report, validation_report, audit_log)
    """
    run_output_dir = OUTPUT_DIR / run_id
    run_log_dir = LOGS_DIR / run_id
    
    if not run_output_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    file_mapping = {
        "classification": run_output_dir / "partner_classification_output.csv",
        "review_queue": run_output_dir / "human_review_queue.csv",
        "summary_report": run_output_dir / "summary_report.md",
        "validation_report": run_output_dir / "validation_report.md",
        "audit_log": run_log_dir / "audit_log.csv"
    }
    
    if file_type not in file_mapping:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
    
    file_path = file_mapping[file_type]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_type}")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='application/octet-stream'
    )


@app.get("/results/{run_id}")
async def get_results(run_id: str):
    """
    Get processing results for a specific run
    
    - **run_id**: Unique identifier for the processing run
    """
    run_output_dir = OUTPUT_DIR / run_id
    
    if not run_output_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    
    try:
        # Load results
        classification_df = pd.read_csv(run_output_dir / "partner_classification_output.csv")
        review_queue_df = pd.read_csv(run_output_dir / "human_review_queue.csv")
        
        # Load summary report
        summary_path = run_output_dir / "summary_report.md"
        with open(summary_path, "r") as f:
            summary_content = f.read()
        
        # Load validation report
        validation_path = run_output_dir / "validation_report.md"
        with open(validation_path, "r") as f:
            validation_content = f.read()
        
        return {
            "run_id": run_id,
            "classification_results": classification_df.to_dict(orient="records"),
            "review_queue": review_queue_df.to_dict(orient="records"),
            "summary_report": summary_content,
            "validation_report": validation_content,
            "total_partners": len(classification_df),
            "escalated_count": int(classification_df['escalate'].sum())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading results: {str(e)}")


# Simple HTML interface for file upload
HTML_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>Micro-Entrepreneur Performance Worker</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .upload-section {
            margin: 20px 0;
            padding: 20px;
            border: 2px dashed #ccc;
            border-radius: 5px;
            text-align: center;
        }
        .upload-section:hover {
            border-color: #007bff;
            background-color: #f9f9f9;
        }
        input[type="file"] {
            margin: 10px 0;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .results {
            margin-top: 30px;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 5px;
            display: none;
        }
        .results h2 {
            color: #333;
        }
        .results ul {
            list-style-type: none;
            padding: 0;
        }
        .results li {
            padding: 10px;
            margin: 5px 0;
            background-color: white;
            border-radius: 3px;
            border-left: 3px solid #007bff;
        }
        .error {
            color: #dc3545;
            padding: 10px;
            background-color: #f8d7da;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        .success {
            color: #155724;
            padding: 10px;
            background-color: #d4edda;
            border-radius: 5px;
            margin-top: 10px;
            display: none;
        }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #007bff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Micro-Entrepreneur Performance Worker</h1>
        <p>Upload a CSV file with partner activity data to automatically classify performance and generate recommendations.</p>
        
        <div class="upload-section">
            <input type="file" id="fileInput" accept=".csv">
            <br>
            <button onclick="uploadFile()" id="uploadBtn">Process CSV File</button>
        </div>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Processing file...</p>
        </div>
        
        <div class="results" id="results">
            <h2>Processing Results</h2>
            <ul id="resultsList"></ul>
            <div id="downloadLinks"></div>
        </div>
    </div>

    <script>
        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) {
                showError('Please select a CSV file');
                return;
            }
            
            if (!file.name.endsWith('.csv')) {
                showError('Only CSV files are supported');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('uploadBtn').disabled = true;
            document.getElementById('error').style.display = 'none';
            document.getElementById('success').style.display = 'none';
            document.getElementById('results').style.display = 'none';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                document.getElementById('loading').style.display = 'none';
                document.getElementById('uploadBtn').disabled = false;
                
                if (response.ok && data.success) {
                    showSuccess('File processed successfully!');
                    displayResults(data);
                } else {
                    const errMsg = data.detail || data.message || 'Unknown error';
                    showError('Processing failed: ' + errMsg);
                }
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('uploadBtn').disabled = false;
                showError('Error uploading file: ' + error.message);
            }
        }
        
        function showError(message) {
            document.getElementById('error').textContent = message;
            document.getElementById('error').style.display = 'block';
        }
        
        function showSuccess(message) {
            document.getElementById('success').textContent = message;
            document.getElementById('success').style.display = 'block';
        }
        
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            const resultsList = document.getElementById('resultsList');
            const downloadLinks = document.getElementById('downloadLinks');
            
            resultsList.innerHTML = '';
            downloadLinks.innerHTML = '';
            
            // Summary
            resultsList.innerHTML += `<li><strong>Total Partners:</strong> ${data.summary.total_partners}</li>`;
            resultsList.innerHTML += `<li><strong>Escalated to Human Review:</strong> ${data.summary.escalated_count}</li>`;
            
            // Classification breakdown
            resultsList.innerHTML += '<li><strong>Classification Breakdown:</strong><ul>';
            for (const [cls, count] of Object.entries(data.summary.classification_breakdown)) {
                resultsList.innerHTML += `<li>${cls}: ${count}</li>`;
            }
            resultsList.innerHTML += '</ul></li>';
            
            // Verification status
            if (data.verification) {
                const status = data.verification.passed ? '✓ PASSED' : '✗ FAILED';
                const color = data.verification.passed ? 'green' : 'red';
                resultsList.innerHTML += `<li><strong>Verification:</strong> <span style="color: ${color}">${status}</span> (${data.verification.passed_checks}/${data.verification.total_checks} checks passed)</li>`;
            }
            
            // Download links
            downloadLinks.innerHTML = '<h3>Download Files:</h3>';
            for (const [fileType, url] of Object.entries(data.output_files)) {
                downloadLinks.innerHTML += `<a href="${url}" download style="margin-right: 15px;">${fileType}</a>`;
            }
            
            resultsDiv.style.display = 'block';
        }
    </script>
</body>
</html>
"""


@app.get("/interface")
async def web_interface():
    """Serve the professional web interface"""
    static_html = STATIC_DIR / "index.html"
    if static_html.exists():
        return FileResponse(static_html, media_type="text/html")
    # Fallback to embedded HTML if static file not found
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=HTML_INTERFACE)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
