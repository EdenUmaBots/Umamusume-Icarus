# Pre Icarus v5.40AI Clock-Aware AI Logs

Pre Icarus v5.40AI expands the AI learning records so clock retry behavior is no longer hidden inside raw race flow.

## What changed

- Race logs now record whether **Burn Clocks** was enabled by the user.
- Each race result can include a `clock_retry` block with the initial rank, final rank, number of clocks used, retry attempt details, and whether the win was rescued by a clock.
- The local `race_outcomes.json` aggregate now tracks clean wins, wins after clock retry, clock retry rate, and clock dependency rate.
- The AI dataset exports those clock fields into `turn_decisions.jsonl` and `career_summaries.jsonl`.
- Smart Race Solver scoring now treats clock-dependent races differently when Burn Clocks is disabled.
- Race logs now include compact master-data enrichment such as fan/reward-set IDs, Trackblazer first-place coin/win-point rewards, venue/date metadata, and official aptitude/performance rate hints when the generated master-data files are available.

## Why this matters

A race that only wins after spending clocks is not as safe as a race that wins cleanly. If the user turns Burn Clocks off, the AI model should not assume that clock rescue is available. These new fields let the model learn separate patterns for:

- races that win cleanly,
- races that lose even with clocks,
- races that often need a clock to become a win,
- races attempted while the user had Burn Clocks disabled.

## Key fields

### `clock_retry`

```json
{
  "user_enabled": true,
  "enabled": true,
  "attempts": 1,
  "used": 1,
  "initial_rank": 4,
  "final_rank": 1,
  "won_before_retry": false,
  "won_after_retry": true,
  "retry_events": []
}
```

### Race outcome aggregate additions

```json
{
  "clean_wins": 8,
  "wins_after_clock": 3,
  "clock_retry_races": 4,
  "clocks_used": 4,
  "clean_win_rate": 0.53,
  "clock_dependency_rate": 0.27
}
```

### Master-data enrichment

```json
{
  "master_metadata": {
    "venue": "Tokyo",
    "fan_set_id": 30,
    "reward_set_id": 100101,
    "fans_first": 10000,
    "trackblazer_coin_first": 100,
    "trackblazer_win_points_first": 100
  },
  "performance_hint": {
    "distance_label": "Long",
    "distance_aptitude": 6,
    "surface_aptitude": 7,
    "running_style_aptitude": 7,
    "aggregate_rate": 9600
  }
}
```

## Safety behavior

Live Policy Assistance remains confidence-gated. The AI can only adjust scores for legal Smart Race Solver candidates. It cannot force unavailable races, override mandatory game states, or enable clock usage if the user turned Burn Clocks off.
