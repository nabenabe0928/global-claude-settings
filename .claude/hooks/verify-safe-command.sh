#!/bin/bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

DANGEROUS_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \."
  "rm -fr \."
  "rm .*-[rR].* \.git([/ ]|$)"
  "rm .*-[rR].* \.claude([/ ]|$)"
  "> /dev/sda"
  "mkfs\."
  "dd if="
  ":\\(\\)\\{:\\|:&\\};:"
  "chmod -R 777 /"
  "curl.*\\| bash"
  "wget.*\\| bash"
  "git( [^ ]+)* commit"
  "git( [^ ]+)* reset .*--hard|git( [^ ]+)* reset --hard"
  "git( [^ ]+)* branch .* -[dD]|git( [^ ]+)* branch -[dD]|git( [^ ]+)* branch .*--delete"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$CMD" | grep -qE "$pattern"; then
    echo "BLOCKED: Detected a dangerous command: $CMD"
    exit 2
  fi
done

if echo "$CMD" | grep -qE "^gh "; then
  if ! echo "$CMD" | grep -qE "^gh ((pr|issue) (list|view)|pr (checkout|diff))"; then
    echo "BLOCKED: Only gh {pr,issue} {list,view}, gh pr checkout, and gh pr diff are allowed. Got: $CMD"
    exit 2
  fi
fi
