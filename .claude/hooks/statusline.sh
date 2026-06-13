#!/usr/bin/env bash
set -euo pipefail

fmt() {
  if [[ -z "$1" || "$1" == "null" ]]
    then echo "0"
  elif (( $(echo "$1 >= 1000000" | bc) ))
    then echo "$(echo "($1+500000)/1000000" | bc)M"
  elif (( $(echo "$1 >= 1000" | bc) ))
    then echo "$(echo "($1+500)/1000" | bc)K"
  else
    echo "$(echo "($1+0.5)/1" | bc)"
  fi
}

status_data=$(cat)
branch_name=$(git branch --show-current 2>/dev/null)

IFS=' ' read -r n_files n_adds n_dels \
  < <(
  git diff --numstat HEAD 2>/dev/null | awk \
  '{n_files++; n_adds+=$1; n_dels+=$2} END {print n_files+0, n_adds+0, n_dels+0}'
)

IFS='|' read -r context_window_size in_token out_token used_pct cache_read cache_write rate_limit_5h rate_limit_7d cost_usd git_worktree thinking effort model_name \
  < <(echo "$status_data" | jq -r '[
    (.context_window.context_window_size // 0),
    (.context_window.total_input_tokens // 0),
    (.context_window.total_output_tokens // 0),
    (.context_window.used_percentage // 0),
    (.context_window.current_usage.cache_read_input_tokens // 0),
    (.context_window.current_usage.cache_creation_input_tokens // 0),
    (.rate_limits.five_hour.used_percentage // 0),
    (.rate_limits.seven_day.used_percentage // 0),
    (.cost.total_cost_usd // 0),
    (.workspace.git_worktree // ""),
    (.thinking.enabled // "true"),
    (.effort.level // "high"),
    (.model.display_name // "Opus")
  ] | map(tostring) | join("|")')

total_tokens=$(fmt "$(echo "$in_token + $out_token" | bc)")

if [[ -n "$git_worktree" ]]
  then git_ref="$git_worktree (from $branch_name)"
else
  git_ref="$branch_name"
fi
if [[ "$thinking" == "true" ]]
  then mode="Think: $effort"
else
  mode="Fast: $effort"
fi

model_msg="$model_name $(fmt $context_window_size) ($mode)"
used_msg="Used: $used_pct% (Session) $rate_limit_5h% (5H), $rate_limit_7d% (7D)"
git_msg="On $git_ref ($n_files Files, +$n_adds/-$n_dels Lines)"
token_msg="Tokens: $total_tokens (In: $(fmt $in_token), Out: $(fmt $out_token))"
session_cost_msg="Session Cost: $(printf "%.2f" $cost_usd) USD"
cache_msg="Cache: $(fmt $cache_read) (Read) / $(fmt $cache_write) (Write)"
echo "$model_msg, $used_msg"
echo "$token_msg, $cache_msg"
echo "$git_msg, $session_cost_msg"
