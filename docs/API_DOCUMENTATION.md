# API Documentation

## Overview

The Micro-Entrepreneur Performance Worker now includes a FastAPI web interface that allows you to upload CSV files and automatically process them through the worker and verification pipeline.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Starting the Server

Start the API server:

```bash
python src/api.py
```

The server will start on `http://localhost:8000`

## Web Interface

Open your browser and navigate to:

```
http://localhost:8000/interface
```

This provides a simple web interface where you can:
- Upload CSV files
- View processing results
- Download output files
- See verification status

## API Endpoints

### POST /upload

Upload a CSV file for automatic processing.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: CSV file as form field named "file"

**Example using curl:**
```bash
curl -X POST -F "file=@data/sample_input.csv" http://localhost:8000/upload
```

**Example using Python requests:**
```python
import requests

with open("data/sample_input.csv", "rb") as f:
    files = {"file": f}
    response = requests.post("http://localhost:8000/upload", files=files)

print(response.json())
```

**Response:**
```json
{
  "success": true,
  "message": "File processed successfully",
  "run_id": "5ea8cfb8-d285-4578-abc2-8c25d4308c9c",
  "timestamp": "2026-08-17T13:27:01.072400",
  "input_file": "sample_input.csv",
  "output_files": {
    "classification": "/download/{run_id}/classification",
    "review_queue": "/download/{run_id}/review_queue",
    "summary_report": "/download/{run_id}/summary_report",
    "validation_report": "/download/{run_id}/validation_report",
    "audit_log": "/download/{run_id}/audit_log"
  },
  "summary": {
    "total_partners": 27,
    "escalated_count": 6,
    "classification_breakdown": {
      "Active": 11,
      "ESCALATE_DATA_ISSUE": 5,
      "Declining": 2,
      "Improving": 2,
      "Inactive": 2,
      "High-Potential": 2,
      "Risky": 2,
      "Active (New, insufficient history)": 1
    },
    "summary_report": "..."
  },
  "verification": {
    "passed": true,
    "total_checks": 15,
    "passed_checks": 15,
    "failed_checks": 0,
    "details": [...]
  }
}
```

### GET /download/{run_id}/{file_type}

Download output files from a specific run.

**Parameters:**
- `run_id`: Unique identifier for the processing run (returned from /upload)
- `file_type`: Type of file to download
  - `classification` - partner_classification_output.csv
  - `review_queue` - human_review_queue.csv
  - `summary_report` - summary_report.md
  - `validation_report` - validation_report.md
  - `audit_log` - audit_log.csv

**Example:**
```bash
curl http://localhost:8000/download/5ea8cfb8-d285-4578-abc2-8c25d4308c9c/classification --output classification.csv
```

### GET /results/{run_id}

Get detailed processing results for a specific run.

**Parameters:**
- `run_id`: Unique identifier for the processing run

**Response:**
```json
{
  "run_id": "5ea8cfb8-d285-4578-abc2-8c25d4308c9c",
  "classification_results": [...],
  "review_queue": [...],
  "summary_report": "...",
  "validation_report": "...",
  "total_partners": 27,
  "escalated_count": 6
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-08-17T13:27:01.072400",
  "service": "Micro-Entrepreneur Performance Worker API"
}
```

### GET /

Root endpoint with API information.

**Response:**
```json
{
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
```

## Automatic Processing

When you upload a CSV file via the API, the following happens automatically:

1. **File Upload**: CSV file is saved to uploads directory
2. **Worker Execution**: The worker processes the file
   - Validates data schema and quality
   - Classifies partners into performance categories
   - Escalates problematic cases to human review
   - Generates all output files
3. **Verification**: The verification script runs automatically
   - Checks 15 Definition of Done criteria
   - Returns verification status in response
4. **Results**: All results are returned in the API response

## CSV File Requirements

The CSV file must contain the following columns:

- partner_id
- partner_name
- region
- onboarding_date
- kyc_status
- active_days_last_30
- txn_count_last_30
- txn_volume_gtv_last_30
- txn_count_prev_30
- txn_volume_gtv_prev_30
- complaints_last_30
- service_uptime_pct
- declared_gtv_last_30
- computed_gtv_last_30_from_daily_logs
- last_txn_date

See `docs/data_dictionary_and_assumptions.md` for detailed field descriptions.

## Error Handling

The API returns appropriate HTTP status codes:

- **200 OK**: Successful processing
- **400 Bad Request**: Invalid file type or missing file
- **404 Not Found**: Run ID or file not found
- **500 Internal Server Error**: Processing or worker execution failed

Error responses include a detailed error message:

```json
{
  "detail": "Error message describing what went wrong"
}
```

## Storage

Uploaded files and outputs are stored in the following directories:

- `uploads/` - Temporary uploaded CSV files
- `api_outputs/` - Generated output files (organized by run_id)
- `api_logs/` - Audit logs (organized by run_id)

These directories are excluded from version control via `.gitignore`.

## Security Considerations

- The API currently accepts all file types but only processes CSV files
- No authentication is implemented (suitable for local/demo use)
- Consider adding authentication for production deployment
- File size limits are not enforced (consider adding for production)

## Production Deployment

For production deployment, consider:

1. **Authentication**: Add API key or OAuth authentication
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **File Size Limits**: Add maximum file size restrictions
4. **Async Processing**: Use background tasks for large files
5. **Database**: Store results in a database instead of file system
6. **HTTPS**: Use HTTPS for secure data transmission
7. **Containerization**: Deploy using Docker for consistency
8. **Monitoring**: Add logging and monitoring

## Example Workflow

1. Start the server:
   ```bash
   python src/api.py
   ```

2. Upload a CSV file via web interface or API:
   ```python
   import requests
   
   with open("my_data.csv", "rb") as f:
       response = requests.post("http://localhost:8000/upload", files={"file": f})
       results = response.json()
       print(f"Processed {results['summary']['total_partners']} partners")
       print(f"Escalated {results['summary']['escalated_count']} to human review")
       print(f"Verification: {'PASSED' if results['verification']['passed'] else 'FAILED'}")
   ```

3. Download output files:
   ```python
   run_id = results['run_id']
   
   # Download classification results
   response = requests.get(f"http://localhost:8000/download/{run_id}/classification")
   with open("classification.csv", "wb") as f:
       f.write(response.content)
   ```

## Troubleshooting

**Server won't start:**
- Check if port 8000 is already in use
- Ensure all dependencies are installed

**Upload fails:**
- Verify the file is a valid CSV
- Check that all required columns are present
- Review the error message in the response

**Verification fails:**
- Check the verification details in the response
- Review the validation_report.md for specific issues
- Ensure the CSV file meets all data quality requirements
