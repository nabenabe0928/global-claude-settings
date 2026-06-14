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

IFS='|' read -r context_window_size in_token out_token used_pct cache_read cache_write rate_limit_5h rate_limit_7d cost_usd git_worktree thinking effort model_name _session_id \
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
    (.model.display_name // "Opus"),
    (.session_id // "")
  ] | map(tostring) | join("|")')

if [[ -n "$_session_id" && "$_session_id" != "null" ]]; then
  _session_dir="$HOME/.claude/status-log/.sessions"
  [[ -d "$_session_dir" ]] || mkdir -p "$_session_dir"
  _tmp_file="$_session_dir/.$_session_id.tmp"
  echo "$status_data" | jq -c '{
    date: (now | strftime("%Y-%m-%d")),
    session_id: .session_id,
    model_id: .model.id,
    project_dir: .workspace.project_dir,
    version: .version,
    cost_usd: .cost.total_cost_usd,
    context_window_size: .context_window.context_window_size,
    used_token_percentage: .context_window.used_percentage,
    input_tokens: .context_window.current_usage.input_tokens,
    output_tokens: .context_window.current_usage.output_tokens,
    cache_write_tokens: .context_window.current_usage.cache_creation_input_tokens,
    cache_read_tokens: .context_window.current_usage.cache_read_input_tokens,
    effort: .effort.level,
    thinking: .thinking.enabled,
    agent_name: .agent.name
  }' > "$_tmp_file" && mv "$_tmp_file" "$_session_dir/$_session_id.json"
fi

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

model_msg="$model_name ($mode)"
used_msg="$rate_limit_5h% (5H), $rate_limit_7d% (7D)"
git_msg="On $git_ref ($n_files Files, +$n_adds/-$n_dels Lines)"
token_msg="Tokens (Used $used_pct%): $total_tokens/$(fmt $context_window_size) (In: $(fmt $in_token), Out: $(fmt $out_token))"
session_cost_msg="Session Cost: $(printf "%.2f" $cost_usd) USD"
cache_msg="Cache: $(fmt $cache_read) (Read) / $(fmt $cache_write) (Write)"
echo "$model_msg, $used_msg"
echo "$token_msg, $cache_msg"
echo "$git_msg, $session_cost_msg"
