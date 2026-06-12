for target in claude_utils claude-official-docs coding-rules hooks skills settings.json
do
    echo cp -r .claude/$target ~/.claude
done

DIR_NOW=$(pwd)
cp pyproject.toml ~/.claude
cp uv.lock ~/.claude
cd ~/.claude && uv sync && cd $DIR_NOW
