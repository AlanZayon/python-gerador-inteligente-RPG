"""Worker uses RAG index/reuse instead of full-book bible."""

from unittest.mock import patch

from tasks.campaign_tasks import process_campaign_generation


@patch("tasks.campaign_tasks.cleanup_temp_files")
@patch("tasks.campaign_tasks._update_progress")
@patch("tasks.campaign_tasks.save_result")
@patch("tasks.campaign_tasks.save_status")
@patch("tasks.campaign_tasks.save_campaign_to_s3")
@patch("tasks.campaign_tasks.validate_campaign", return_value=(True, [], 90))
@patch("tasks.campaign_tasks.complete", return_value="# Overview\nSession 1\nReady.")
@patch("tasks.campaign_tasks.is_configured", return_value=True)
@patch("services.rag.context_packer.pack_campaign_context")
@patch("services.rag.indexer.ensure_indexed")
@patch("tasks.campaign_tasks.validate_pdf", return_value=(True, "OK"))
@patch("tasks.campaign_tasks.download_file_from_s3", return_value="/tmp/book.pdf")
def test_process_campaign_reuses_index_and_packed_context(
    mock_download,
    mock_validate,
    mock_ensure,
    mock_pack,
    mock_configured,
    mock_complete,
    mock_quality,
    mock_upload,
    mock_save_status,
    mock_save_result,
    mock_progress,
    mock_cleanup,
):
    mock_ensure.return_value = {
        "book_id": "bk_deadbeef",
        "index_reused": True,
        "chunk_count": 12,
        "skipped": True,
    }
    mock_pack.return_value = {
        "book_context": "The city of Valdris drowns. Sahuagin rule the trenches.",
        "key_terms": ["Valdris", "Sahuagin"],
        "chunks_used": 4,
        "token_count": 420,
        "setting": "Valdris drowns",
    }
    mock_upload.return_value = {"file_url": "https://s3/campaign.md", "s3_key": "campaigns/x.md"}

    result = process_campaign_generation(
        job_id="job-1",
        file_url="https://s3/book.pdf",
        filename="book.pdf",
        target_language="en",
        campaign_complexity="simples",
        system_preset="generic",
        theme="sunken city",
    )

    assert result is not None
    mock_ensure.assert_called_once()
    mock_pack.assert_called_once()
    assert result["book_id"] == "bk_deadbeef"
    assert result["index_reused"] is True
    assert result["chunks_used"] == 4
    prompt = mock_complete.call_args[0][0]
    assert "Valdris" in prompt
    assert "BOOK CONTEXT" in prompt
