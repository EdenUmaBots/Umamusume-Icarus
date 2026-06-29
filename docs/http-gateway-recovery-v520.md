# HTTP Gateway Recovery v5.20

Pre Icarus v5.20 treats temporary HTTP gateway/server failures as recoverable during career automation.

## Fixed

`single_mode_free/check_event` can occasionally return HTTP 502, 503, or 504 when the upstream game server is slow or overloaded. Earlier builds retried raw network exceptions, but a real HTTP 504 response escaped immediately and could crash the career runner.

## Behavior

The API client now retries HTTP 502/503/504 responses with bounded backoff before raising. If the retry budget is exhausted, the runner classifies the resulting HTTP 502/503/504 exception as recoverable, reloads career state, and attempts to continue through the existing recovery path.

This is especially helpful after races or event transitions where the next call is `single_mode_free/check_event`.

## Safety

This does not retry permanent request errors such as API result codes 213, 500, or 501. It only handles temporary gateway/server HTTP statuses.
