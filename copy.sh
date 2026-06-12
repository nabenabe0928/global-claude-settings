for target in claude_utils claude-official-docs coding-rules hooks skills settings.json
do
    echo cp -r .claude/$target ~/.claude
done
