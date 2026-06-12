cd .claude
ruff format tests/ claude_utils/
ruff check --fix tests/ claude_utils/
python -m pytest tests 
cd ..
