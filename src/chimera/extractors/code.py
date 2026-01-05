"""Code extractors (Python, JavaScript, TypeScript, YAML, JSON)."""

import ast
import json
from pathlib import Path

import yaml

from chimera.extractors.base import BaseExtractor, ExtractionResult
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class PythonExtractor(BaseExtractor):
    """Extract content and structure from Python files."""
    
    name = "python"
    extensions = ["py", "pyw"]
    mime_types = ["text/x-python"]
    
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract code structure from Python file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Parse AST
            try:
                tree = ast.parse(content)
                code_elements = self._extract_elements(tree)
            except SyntaxError as e:
                # Still return content even if AST parsing fails
                code_elements = []
                logger.warning(f"Python AST parse failed: {file_path}: {e}")
            
            return ExtractionResult(
                file_path=file_path,
                content=content,
                metadata={
                    "language": "python",
                    "line_count": len(content.splitlines()),
                },
                code_elements=code_elements,
                word_count=self.count_words(content),
            )
        except Exception as e:
            logger.error(f"Python extraction failed: {file_path}: {e}")
            return ExtractionResult(
                file_path=file_path,
                content="",
                success=False,
                error=str(e),
            )
    
    def _extract_elements(self, tree: ast.AST) -> list[dict]:
        """Extract functions and classes from AST."""
        elements = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                elements.append({
                    "element_type": "function",
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                })
            elif isinstance(node, ast.AsyncFunctionDef):
                elements.append({
                    "element_type": "async_function",
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "args": [arg.arg for arg in node.args.args],
                })
            elif isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body 
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                elements.append({
                    "element_type": "class",
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": methods,
                    "bases": [self._get_name(b) for b in node.bases],
                })
        
        return elements
    
    def _get_decorator_name(self, node: ast.expr) -> str:
        """Get decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "unknown"
    
    def _get_name(self, node: ast.expr) -> str:
        """Get name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return "unknown"


class JavaScriptExtractor(BaseExtractor):
    """Extract content from JavaScript/TypeScript files."""
    
    name = "javascript"
    extensions = ["js", "jsx", "ts", "tsx", "mjs"]
    mime_types = ["application/javascript", "text/typescript"]
    
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from JS/TS file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            ext = self.get_extension(file_path)
            
            # Basic analysis without full parsing
            # TODO: Use tree-sitter for proper parsing
            
            # Count functions (rough estimate)
            function_count = content.count("function ") + content.count("=> ")
            
            # Detect framework
            framework = None
            if "import React" in content or "from 'react'" in content:
                framework = "react"
            elif "@Component" in content:
                framework = "angular"
            elif "Vue." in content or "createApp" in content:
                framework = "vue"
            
            return ExtractionResult(
                file_path=file_path,
                content=content,
                metadata={
                    "language": "typescript" if ext in ["ts", "tsx"] else "javascript",
                    "react": ext in ["jsx", "tsx"],
                    "line_count": len(content.splitlines()),
                    "function_count": function_count,
                    "framework": framework,
                },
                word_count=self.count_words(content),
            )
        except Exception as e:
            logger.error(f"JavaScript extraction failed: {file_path}: {e}")
            return ExtractionResult(
                file_path=file_path,
                content="",
                success=False,
                error=str(e),
            )


class YAMLExtractor(BaseExtractor):
    """Extract content from YAML files."""
    
    name = "yaml"
    extensions = ["yaml", "yml"]
    mime_types = ["application/x-yaml"]
    
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from YAML file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Parse YAML to extract structure
            try:
                data = yaml.safe_load(content)
                top_keys = list(data.keys()) if isinstance(data, dict) else []
            except yaml.YAMLError:
                data = None
                top_keys = []
            
            return ExtractionResult(
                file_path=file_path,
                content=content,
                metadata={
                    "format": "yaml",
                    "top_keys": top_keys[:20],  # First 20 keys
                    "line_count": len(content.splitlines()),
                },
                word_count=self.count_words(content),
            )
        except Exception as e:
            logger.error(f"YAML extraction failed: {file_path}: {e}")
            return ExtractionResult(
                file_path=file_path,
                content="",
                success=False,
                error=str(e),
            )


class JSONExtractor(BaseExtractor):
    """Extract content from JSON files."""
    
    name = "json"
    extensions = ["json"]
    mime_types = ["application/json"]
    
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from JSON file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Parse JSON to extract structure
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    top_keys = list(data.keys())[:20]
                    item_count = len(data)
                elif isinstance(data, list):
                    top_keys = []
                    item_count = len(data)
                else:
                    top_keys = []
                    item_count = 1
            except json.JSONDecodeError:
                top_keys = []
                item_count = 0
            
            return ExtractionResult(
                file_path=file_path,
                content=content,
                metadata={
                    "format": "json",
                    "top_keys": top_keys,
                    "item_count": item_count,
                    "line_count": len(content.splitlines()),
                },
                word_count=self.count_words(content),
            )
        except Exception as e:
            logger.error(f"JSON extraction failed: {file_path}: {e}")
            return ExtractionResult(
                file_path=file_path,
                content="",
                success=False,
                error=str(e),
            )
