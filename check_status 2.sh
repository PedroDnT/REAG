 #!/bin/bash
  echo "=== REAG Project Status ==="
  echo ""
  echo "📁 Files created:"
  find . -name "*.py" -not -path "./venv/*" | wc -l | xargs echo "  Python files:"
  find . -name "*.ipynb" | wc -l | xargs echo "  Notebooks:"
  echo ""
  echo "🧪 Tests:"
  pytest tests/ -q 2>/dev/null && echo "  ✅ Tests passing" || echo "  ⚠️  Tests not ready/failing"
  echo ""
  echo "📝 Recent commits:"
  git log --oneline -5
  

