from services.job_status import save_status, get_status, build_api_response, mark_failed, mark_processing


def test_save_and_get_status(mock_redis):
    job_id = "3e6a6f6e-0d41-4f15-b1e9-bf8a80fd497b"

    mark_processing(job_id, "Downloading...", conn=mock_redis)
    data = get_status(job_id, conn=mock_redis)

    assert data["status"] == "processing"
    assert data["progress"] == "Downloading..."

    mark_failed(job_id, "Something broke", conn=mock_redis)
    data = get_status(job_id, conn=mock_redis)

    assert data["status"] == "failed"
    assert data["error"] == "Something broke"


def test_completed_result(mock_redis):
    job_id = "75ca2562-14d9-4a7d-a51c-77654bdecbff"
    result = {
        "campaign_url": "https://example.com/c.md",
        "s3_key": "campaigns/c.md",
        "preview": "Hello",
        "file_size": 100,
    }
    save_status(job_id, "completed", result, conn=mock_redis)
    data = get_status(job_id, conn=mock_redis)

    assert data["status"] == "completed"
    assert data["data"]["campaign_url"] == "https://example.com/c.md"


def test_build_api_response(mock_redis):
    job_id = "3e6a6f6e-0d41-4f15-b1e9-bf8a80fd497b"
    mark_processing(job_id, "Extracting text...", conn=mock_redis)
    status_data = get_status(job_id, conn=mock_redis)
    response = build_api_response(job_id, status_data)

    assert response["job_id"] == job_id
    assert response["progress"] == "Extracting text..."
    assert response["status"] == "processing"
