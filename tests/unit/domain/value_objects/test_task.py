"""Tests for Task value object.

TDD Red Phase: These tests define expected behavior before implementation.
"""


class TestTaskCreation:
    """Test Task value object creation."""

    def test_create_with_required_fields(self):
        """Test creating Task with required fields."""
        import uuid

        from src.domain.value_objects.task import UDMRTask

        task_id = uuid.uuid4()
        task = UDMRTask(
            task_id=task_id,
            input="Test input data",
            data_residency="CHINA_DOMESTIC",
            preferred_model="model-1",
            allowed_models=["model-1", "model-2"],
        )

        assert task.task_id == task_id
        assert task.input == "Test input data"
        assert task.data_residency == "CHINA_DOMESTIC"
        assert task.preferred_model == "model-1"
        assert task.allowed_models == ["model-1", "model-2"]

    def test_create_with_defaults(self):
        """Test creating Task with default values."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(
            input="Test data",
        )

        assert task.data_residency == "CHINA_DOMESTIC"
        assert task.preferred_model == ""
        assert task.allowed_models == []


class TestTaskMethods:
    """Test Task business methods."""

    def test_is_china_domestic_true(self):
        """Test is_china_domestic returns True for CHINA_DOMESTIC."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(data_residency="CHINA_DOMESTIC")
        assert task.is_china_domestic() is True

    def test_is_china_domestic_false(self):
        """Test is_china_domestic returns False for non-domestic."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(data_residency="OVERSEAS")
        assert task.is_china_domestic() is False

    def test_requires_local_processing_true(self):
        """Test requires_local_processing returns True for CHINA_DOMESTIC."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(data_residency="CHINA_DOMESTIC")
        assert task.requires_local_processing() is True

    def test_requires_local_processing_false_for_overseas(self):
        """Test requires_local_processing returns False for OVERSEAS."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(data_residency="OVERSEAS")
        assert task.requires_local_processing() is False

    def test_requires_local_processing_false_for_hkmo(self):
        """Test requires_local_processing returns False for CHINA_HKMO."""
        from src.domain.value_objects.task import UDMRTask

        task = UDMRTask(data_residency="CHINA_HKMO")
        assert task.requires_local_processing() is False

    def test_get_task_context(self):
        """Test get_task_context returns correct dict for UDMR."""
        import uuid

        from src.domain.value_objects.task import UDMRTask

        task_id = uuid.uuid4()
        task = UDMRTask(
            task_id=task_id,
            input="Test data",
            data_residency="CHINA_DOMESTIC",
            preferred_model="model-x",
            allowed_models=["model-x", "model-y"],
        )

        ctx = task.get_task_context()
        assert ctx["task_id"] == str(task_id)
        assert ctx["session_id"] == str(task_id)
        assert ctx["complexity"] == "high"
        assert ctx["data_residency"] == "CHINA_DOMESTIC"
