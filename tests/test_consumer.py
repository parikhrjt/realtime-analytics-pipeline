"""Tests for event processor with mocked storage."""


import pytest
from conftest import FakePostgresStore, FakeRedisCache

from app.consumer.processor import EventProcessor


class TestEventProcessor:
    @pytest.fixture
    def processor(self):
        store = FakePostgresStore()
        cache = FakeRedisCache()
        return EventProcessor(store=store, cache=cache)

    def test_process_valid_event(self, processor, sample_page_view_event):
        result = processor.process_message(sample_page_view_event)
        assert result["event_type"] == "page_view"
        assert len(processor.store.raw_events) == 1

    def test_kpi_refresh_after_threshold(self, processor, sample_page_view_event):
        processor._kpi_refresh_every = 2
        processor.process_message(sample_page_view_event)
        result = processor.process_message(sample_page_view_event)
        assert result["kpi_refreshed"] is True
        assert processor.cache.payload is not None

    def test_invalid_event_raises(self, processor):
        with pytest.raises(Exception):
            processor.process_message({"event_type": "invalid"})
