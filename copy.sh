for target in claude_utils claude-official-docs coding-rules hooks rules skills settings.json
do
    cp -r .claude/$target ~/.claude
done

DIR_NOW=$(pwd)
cp pyproject.toml ~/.claude
cp uv.lock ~/.claude
cd ~/.claude && uv sync && cd $DIR_NOW
