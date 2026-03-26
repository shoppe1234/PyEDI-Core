"""Tests for pyedi_core.validator module."""

import dataclasses
import json

import pytest

from pyedi_core.validator import (
    ValidationResult,
    check_compilation_warnings,
    check_type_preservation,
    compile_and_write,
    validate,
)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCompileAndWrite:
    def test_compile_and_write_produces_yaml(self, tmp_path):
        compiled_yaml, yaml_path, record_defs = compile_and_write(
            "tpm810SourceFF.txt", compiled_dir=str(tmp_path)
        )
        assert "schema" in compiled_yaml
        assert "mapping" in compiled_yaml
        assert len(compiled_yaml["schema"]["columns"]) > 0
        from pathlib import Path
        assert Path(yaml_path).exists()


@pytest.mark.unit
class TestTypePreservation:
    def test_type_preservation_correct_tpm(self, tmp_path):
        compiled_yaml, _, record_defs = compile_and_write(
            "tpm810SourceFF.txt", compiled_dir=str(tmp_path)
        )
        warnings = check_type_preservation(record_defs, compiled_yaml)
        assert len(warnings) == 0, f"Unexpected type warnings: {warnings}"

    def test_type_preservation_fixed_gfs(self, tmp_path):
        compiled_yaml, _, record_defs = compile_and_write(
            "schemas/source/gfsGenericOut810FF.txt", compiled_dir=str(tmp_path)
        )
        cols = {c["name"]: c["type"] for c in compiled_yaml["schema"]["columns"]}
        assert cols.get("CaseSize") == "float", f"CaseSize is {cols.get('CaseSize')}"
        assert cols.get("CasePrice") == "float", f"CasePrice is {cols.get('CasePrice')}"


@pytest.mark.unit
class TestFieldIdentifierCollision:
    def test_fieldidentifier_collision_handled(self, tmp_path):
        compiled_yaml, _, _ = compile_and_write(
            "schemas/source/gfsGenericOut810FF.txt", compiled_dir=str(tmp_path)
        )
        records = compiled_yaml["schema"]["records"]
        assert len(records) > 0, "records is empty — collision not handled"


@pytest.mark.unit
class TestCompilationWarnings:
    def test_check_compilation_warnings_collision(self):
        from pyedi_core.core.schema_compiler import parse_dsl_file
        record_defs, _, _ = parse_dsl_file("schemas/source/gfsGenericOut810FF.txt")
        warnings = check_compilation_warnings(record_defs)
        assert any("collision" in w for w in warnings)


@pytest.mark.unit
class TestValidateErrors:
    def test_validate_missing_dsl(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate("nonexistent_file.txt", compiled_dir=str(tmp_path))

    def test_validate_json_serializable(self, tmp_path):
        result = validate("tpm810SourceFF.txt", compiled_dir=str(tmp_path))
        data = dataclasses.asdict(result)
        serialized = json.dumps(data, default=str)
        assert len(serialized) > 0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRunSample:
    def test_run_sample_produces_traces(self, tmp_path):
        result = validate(
            "tpm810SourceFF.txt",
            sample_path="tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt",
            compiled_dir=str(tmp_path),
        )
        assert result.field_traces is not None
        assert len(result.field_traces) == 3

    def test_coverage_report_counts(self, tmp_path):
        result = validate(
            "tpm810SourceFF.txt",
            sample_path="tests/user_supplied/inputs/NA_810_MARGINEDGE_20260129.txt",
            compiled_dir=str(tmp_path),
        )
        assert result.coverage is not None
        assert result.coverage.source_fields_total > 0
        assert result.coverage.coverage_pct > 0.0
        assert result.coverage.coverage_pct <= 100.0
