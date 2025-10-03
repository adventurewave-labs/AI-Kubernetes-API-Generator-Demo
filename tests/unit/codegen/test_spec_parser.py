"""
Unit tests for the OpenAPI specification parser functionality.
Tests the parsing and validation of API specifications.
"""

import pytest
import json
from pathlib import Path

# Import the codegen modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from codegen.spec_parser import (
    OpenAPISpecParser,
    SpecValidator,
    SpecTransformer,
    SpecValidationError
)
from codegen.models import (
    APISpecification,
    FieldDefinition,
    FieldTypes
)


class TestOpenAPISpecParser:
    """Test the OpenAPI specification parser."""

    @pytest.fixture
    def spec_parser(self):
        """Create a spec parser instance."""
        return OpenAPISpecParser()

    def test_parse_minimal_valid_spec(self, spec_parser):
        """Test parsing a minimal valid API specification."""
        spec = {
            "group": "platform.test.io",
            "version": "v1alpha1",
            "kind": "TestResource",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

        api_spec = spec_parser.parse(spec)

        assert api_spec.group == "platform.test.io"
        assert api_spec.version == "v1alpha1"
        assert api_spec.kind == "TestResource"
        assert "name" in api_spec.spec.properties
        assert api_spec.spec.properties["name"].type == FieldTypes.STRING

    def test_parse_complex_spec_with_multiple_fields(self, spec_parser):
        """Test parsing a complex specification with multiple fields."""
        spec = {
            "group": "database.example.io",
            "version": "v1beta1",
            "kind": "Database",
            "spec": {
                "properties": {
                    "engine": {"type": "string"},
                    "replicas": {"type": "integer"},
                    "enabled": {"type": "boolean"},
                    "config": {"type": "object"}
                }
            }
        }

        api_spec = spec_parser.parse(spec)

        assert api_spec.group == "database.example.io"
        assert api_spec.version == "v1beta1"
        assert api_spec.kind == "Database"
        assert len(api_spec.spec.properties) == 4
        assert api_spec.spec.properties["engine"].type == FieldTypes.STRING
        assert api_spec.spec.properties["replicas"].type == FieldTypes.INTEGER
        assert api_spec.spec.properties["enabled"].type == FieldTypes.BOOLEAN
        assert api_spec.spec.properties["config"].type == FieldTypes.OBJECT

    def test_parse_spec_with_nested_properties(self, spec_parser):
        """Test parsing specification with nested object properties."""
        spec = {
            "group": "storage.example.io",
            "version": "v1",
            "kind": "Storage",
            "spec": {
                "properties": {
                    "capacity": {
                        "type": "object",
                        "properties": {
                            "size": {"type": "string"},
                            "unit": {"type": "string"}
                        }
                    }
                }
            }
        }

        api_spec = spec_parser.parse(spec)

        assert api_spec.spec.properties["capacity"].type == FieldTypes.OBJECT
        assert hasattr(api_spec.spec.properties["capacity"], "properties")
        assert "size" in api_spec.spec.properties["capacity"].properties

    def test_parse_spec_with_array_types(self, spec_parser):
        """Test parsing specification with array field types."""
        spec = {
            "group": "example.io",
            "version": "v1",
            "kind": "ArrayResource",
            "spec": {
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "ports": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                }
            }
        }

        api_spec = spec_parser.parse(spec)

        assert api_spec.spec.properties["tags"].type == FieldTypes.ARRAY
        assert api_spec.spec.properties["tags"].items.type == FieldTypes.STRING
        assert api_spec.spec.properties["ports"].type == FieldTypes.ARRAY
        assert api_spec.spec.properties["ports"].items.type == FieldTypes.INTEGER

    def test_parse_invalid_spec_missing_required_fields(self, spec_parser):
        """Test parsing specification with missing required fields."""
        invalid_specs = [
            {},  # Empty spec
            {"group": "test.io"},  # Missing version, kind, spec
            {"group": "test.io", "version": "v1"},  # Missing kind, spec
            {"group": "test.io", "version": "v1", "kind": "Test"},  # Missing spec
            {"group": "test.io", "version": "v1", "kind": "Test", "spec": {}},  # Empty spec
        ]

        for spec in invalid_specs:
            with pytest.raises(SpecValidationError):
                spec_parser.parse(spec)

    def test_parse_spec_with_invalid_field_types(self, spec_parser):
        """Test parsing specification with invalid field types."""
        spec = {
            "group": "test.io",
            "version": "v1",
            "kind": "Test",
            "spec": {
                "properties": {
                    "invalid_field": {"type": "invalid_type"}
                }
            }
        }

        with pytest.raises(SpecValidationError):
            spec_parser.parse(spec)

    def test_parse_spec_from_json_string(self, spec_parser):
        """Test parsing specification from JSON string."""
        json_spec = json.dumps({
            "group": "test.io",
            "version": "v1",
            "kind": "Test",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        })

        api_spec = spec_parser.parse_from_json(json_spec)

        assert api_spec.group == "test.io"
        assert api_spec.kind == "Test"

    def test_parse_spec_from_yaml_string(self, spec_parser):
        """Test parsing specification from YAML string."""
        yaml_spec = """
group: test.io
version: v1
kind: Test
spec:
  properties:
    name:
      type: string
"""

        api_spec = spec_parser.parse_from_yaml(yaml_spec)

        assert api_spec.group == "test.io"
        assert api_spec.kind == "Test"

    def test_parse_spec_from_file(self, spec_parser, temp_dir):
        """Test parsing specification from file."""
        spec_file = temp_dir / "spec.json"
        spec_data = {
            "group": "test.io",
            "version": "v1",
            "kind": "Test",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

        with open(spec_file, 'w') as f:
            json.dump(spec_data, f)

        api_spec = spec_parser.parse_from_file(spec_file)

        assert api_spec.group == "test.io"
        assert api_spec.kind == "Test"


class TestSpecValidator:
    """Test the specification validator."""

    @pytest.fixture
    def validator(self):
        """Create a spec validator instance."""
        return SpecValidator()

    def test_validate_valid_spec(self, validator):
        """Test validation of a valid specification."""
        spec = APISpecification(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec=FieldDefinition(type="object", properties={
                "name": FieldDefinition(type="string")
            })
        )

        errors = validator.validate(spec)
        assert len(errors) == 0

    def test_validate_group_naming_convention(self, validator):
        """Test validation of group naming convention."""
        invalid_groups = [
            "invalid-group",
            "invalid.group",
            "group",
            "test.io/v1",
            "",
            "very.long.domain.name.that.exceeds.reasonable.length.example.io"
        ]

        for group in invalid_groups:
            spec = APISpecification(
                group=group,
                version="v1",
                kind="Test",
                spec=FieldDefinition(type="object")
            )

            errors = validator.validate(spec)
            assert len(errors) > 0
            assert any("group" in str(error).lower() for error in errors)

    def test_validate_version_format(self, validator):
        """Test validation of version format."""
        invalid_versions = [
            "v1",  # Missing alpha/beta
            "v1alpha",  # Missing number
            "v1.1",  # Invalid format
            "alpha1",  # Missing v
            "",
            "v999alpha1"  # Unreasonably high version
        ]

        for version in invalid_versions:
            spec = APISpecification(
                group="test.io",
                version=version,
                kind="Test",
                spec=FieldDefinition(type="object")
            )

            errors = validator.validate(spec)
            assert len(errors) > 0
            assert any("version" in str(error).lower() for error in errors)

    def test_validate_kind_naming(self, validator):
        """Test validation of kind naming convention."""
        invalid_kinds = [
            "invalid_kind",  # snake_case
            "Invalid-Kind",  # hyphen
            "kind",  # lowercase
            "KIND",  # uppercase
            "VeryVeryLongKindNameThatExceedsReasonableLength",
            "",
            "123Kind",  # starts with number
            "Kind@Name"  # invalid characters
        ]

        for kind in invalid_kinds:
            spec = APISpecification(
                group="test.io",
                version="v1alpha1",
                kind=kind,
                spec=FieldDefinition(type="object")
            )

            errors = validator.validate(spec)
            assert len(errors) > 0
            assert any("kind" in str(error).lower() for error in errors)

    def test_validate_field_limits(self, validator):
        """Test validation of field count limits."""
        # Create spec with too many fields
        properties = {}
        for i in range(60):  # Exceeds reasonable limit
            properties[f"field_{i}"] = FieldDefinition(type="string")

        spec = APISpecification(
            group="test.io",
            version="v1alpha1",
            kind="Test",
            spec=FieldDefinition(type="object", properties=properties)
        )

        errors = validator.validate(spec)
        assert len(errors) > 0
        assert any("field" in str(error).lower() for error in errors)

    def test_validate_field_names(self, validator):
        """Test validation of field names."""
        invalid_field_names = [
            "InvalidName",  # CamelCase in JSON
            "invalid-name",  # hyphen
            "field name",  # space
            "field@name",  # invalid character
            "123field",  # starts with number
            "",  # empty
            "this_field_name_is_extremely_long_and_exceeds_reasonable_limits_for_json_field_names"
        ]

        for field_name in invalid_field_names:
            spec = APISpecification(
                group="test.io",
                version="v1alpha1",
                kind="Test",
                spec=FieldDefinition(type="object", properties={
                    field_name: FieldDefinition(type="string")
                })
            )

            errors = validator.validate(spec)
            assert len(errors) > 0
            assert any("field" in str(error).lower() for error in errors)

    def test_validate_field_types(self, validator):
        """Test validation of field types."""
        spec = APISpecification(
            group="test.io",
            version="v1alpha1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "invalid_field": FieldDefinition(type="invalid_type")
            })
        )

        errors = validator.validate(spec)
        assert len(errors) > 0
        assert any("type" in str(error).lower() for error in errors)

    def test_validate_required_fields_in_array_items(self, validator):
        """Test validation of array item field definitions."""
        spec = APISpecification(
            group="test.io",
            version="v1alpha1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "tags": FieldDefinition(
                    type="array",
                    items=FieldDefinition(type="invalid_type")
                )
            })
        )

        errors = validator.validate(spec)
        assert len(errors) > 0


class TestSpecTransformer:
    """Test the specification transformer."""

    @pytest.fixture
    def transformer(self):
        """Create a spec transformer instance."""
        return SpecTransformer()

    def test_transform_spec_to_openapi_schema(self, transformer):
        """Test transforming API spec to OpenAPI schema."""
        spec = APISpecification(
            group="platform.test.io",
            version="v1alpha1",
            kind="VectorDB",
            spec=FieldDefinition(type="object", properties={
                "engine_type": FieldDefinition(type="string"),
                "replicas": FieldDefinition(type="integer"),
                "enabled": FieldDefinition(type="boolean"),
                "config": FieldDefinition(type="object")
            })
        )

        openapi_schema = transformer.to_openapi_schema(spec)

        assert openapi_schema["type"] == "object"
        assert "properties" in openapi_schema
        assert len(openapi_schema["properties"]) == 4
        assert openapi_schema["properties"]["engine_type"]["type"] == "string"
        assert openapi_schema["properties"]["replicas"]["type"] == "integer"
        assert openapi_schema["properties"]["enabled"]["type"] == "boolean"
        assert openapi_schema["properties"]["config"]["type"] == "object"

    def test_transform_spec_to_crd_yaml(self, transformer):
        """Test transforming API spec to CRD YAML."""
        spec = APISpecification(
            group="platform.test.io",
            version="v1alpha1",
            kind="VectorDB",
            spec=FieldDefinition(type="object", properties={
                "engine_type": FieldDefinition(type="string")
            })
        )

        crd_yaml = transformer.to_crd_yaml(spec)

        assert "apiVersion: apiextensions.k8s.io/v1" in crd_yaml
        assert "kind: CustomResourceDefinition" in crd_yaml
        assert "name: vectordbs.platform.test.io" in crd_yaml
        assert "group: platform.test.io" in crd_yaml
        assert "kind: VectorDB" in crd_yaml

    def test_transform_spec_to_go_types(self, transformer):
        """Test transforming API spec to Go type definitions."""
        spec = APISpecification(
            group="platform.test.io",
            version="v1alpha1",
            kind="VectorDB",
            spec=FieldDefinition(type="object", properties={
                "engine_type": FieldDefinition(type="string"),
                "replicas": FieldDefinition(type="integer", description="Number of replicas")
            })
        )

        go_code = transformer.to_go_types(spec, "pkg/apis")

        assert "package v1alpha1" in go_code
        assert "type VectorDBSpec struct" in go_code
        assert "EngineType string `json:\"engineType\"`" in go_code
        assert "Replicas int `json:\"replicas\"`" in go_code

    def test_transform_spec_with_custom_package_name(self, transformer):
        """Test transforming spec with custom package name."""
        spec = APISpecification(
            group="test.io",
            version="v1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "name": FieldDefinition(type="string")
            })
        )

        go_code = transformer.to_go_types(spec, "custom/package/name")

        assert "package v1" in go_code
        assert "type TestSpec struct" in go_code

    def test_transform_spec_to_markdown_documentation(self, transformer):
        """Test transforming spec to Markdown documentation."""
        spec = APISpecification(
            group="platform.test.io",
            version="v1alpha1",
            kind="VectorDB",
            spec=FieldDefinition(type="object", properties={
                "engine_type": FieldDefinition(type="string", description="Database engine type"),
                "replicas": FieldDefinition(type="integer", description="Number of replicas")
            })
        )

        markdown = transformer.to_markdown_doc(spec)

        assert "# VectorDB" in markdown
        assert "## API Version" in markdown
        assert "v1alpha1" in markdown
        assert "## Fields" in markdown
        assert "engine_type" in markdown
        assert "replicas" in markdown

    def test_transform_spec_to_json_schema(self, transformer):
        """Test transforming spec to JSON Schema."""
        spec = APISpecification(
            group="test.io",
            version="v1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "name": FieldDefinition(type="string")
            })
        )

        json_schema = transformer.to_json_schema(spec)

        assert json_schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert json_schema["type"] == "object"
        assert "properties" in json_schema
        assert json_schema["properties"]["name"]["type"] == "string"

    def test_transform_spec_with_nested_objects(self, transformer):
        """Test transforming spec with nested object properties."""
        nested_field = FieldDefinition(
            type="object",
            properties={
                "size": FieldDefinition(type="string"),
                "unit": FieldDefinition(type="string")
            }
        )

        spec = APISpecification(
            group="test.io",
            version="v1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "capacity": nested_field
            })
        )

        openapi_schema = transformer.to_openapi_schema(spec)

        assert openapi_schema["properties"]["capacity"]["type"] == "object"
        assert "properties" in openapi_schema["properties"]["capacity"]
        assert openapi_schema["properties"]["capacity"]["properties"]["size"]["type"] == "string"

    def test_transform_spec_with_arrays(self, transformer):
        """Test transforming spec with array fields."""
        array_field = FieldDefinition(
            type="array",
            items=FieldDefinition(type="string")
        )

        spec = APISpecification(
            group="test.io",
            version="v1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "tags": array_field
            })
        )

        openapi_schema = transformer.to_openapi_schema(spec)

        assert openapi_schema["properties"]["tags"]["type"] == "array"
        assert openapi_schema["properties"]["tags"]["items"]["type"] == "string"

    @pytest.mark.parametrize("format_type", ["openapi", "crd", "go", "markdown", "json-schema"])
    def test_transform_spec_to_different_formats(self, transformer, format_type):
        """Test transforming spec to different output formats."""
        spec = APISpecification(
            group="test.io",
            version="v1",
            kind="Test",
            spec=FieldDefinition(type="object", properties={
                "name": FieldDefinition(type="string")
            })
        )

        if format_type == "openapi":
            result = transformer.to_openapi_schema(spec)
            assert isinstance(result, dict)
        elif format_type == "crd":
            result = transformer.to_crd_yaml(spec)
            assert isinstance(result, str)
        elif format_type == "go":
            result = transformer.to_go_types(spec)
            assert isinstance(result, str)
        elif format_type == "markdown":
            result = transformer.to_markdown_doc(spec)
            assert isinstance(result, str)
        elif format_type == "json-schema":
            result = transformer.to_json_schema(spec)
            assert isinstance(result, dict)


class TestFieldDefinition:
    """Test the FieldDefinition model."""

    def test_field_definition_creation(self):
        """Test creating a field definition."""
        field = FieldDefinition(
            type="string",
            description="Test field",
            required=True,
            default="default_value"
        )

        assert field.type == "string"
        assert field.description == "Test field"
        assert field.required is True
        assert field.default == "default_value"

    def test_field_definition_validation(self):
        """Test field definition validation."""
        # Valid field
        field = FieldDefinition(type="string")
        assert field.is_valid() is True

        # Invalid field type
        field = FieldDefinition(type="invalid_type")
        assert field.is_valid() is False

        # Array with missing items
        field = FieldDefinition(type="array")
        assert field.is_valid() is False

        # Array with valid items
        field = FieldDefinition(
            type="array",
            items=FieldDefinition(type="string")
        )
        assert field.is_valid() is True

    def test_field_definition_to_dict(self):
        """Test converting field definition to dictionary."""
        field = FieldDefinition(
            type="string",
            description="Test field",
            required=True
        )

        field_dict = field.to_dict()

        assert field_dict["type"] == "string"
        assert field_dict["description"] == "Test field"
        assert field_dict["required"] is True

    def test_field_definition_from_dict(self):
        """Test creating field definition from dictionary."""
        field_dict = {
            "type": "string",
            "description": "Test field",
            "required": True
        }

        field = FieldDefinition.from_dict(field_dict)

        assert field.type == "string"
        assert field.description == "Test field"
        assert field.required is True