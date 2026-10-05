# Generated practice response cleanup — October 5, 2026

Closing the public generated-practice SSE response now awaits its inner
generator. Previously, closure at `started` or `progress` returned while the
run remained `running`; prompt/message cleanup and provider closure depended
on later async-generator finalisation. The existing inner cleanup is now
enclosed with `contextlib.aclosing` at the public response boundary.

Four new regression cases cover study and temporary contexts at both closure
points. They assert cancellation immediately after `aclose`, one terminal
event, erased prompt/messages, closed provider iteration and no committed
practice/evidence. Temporary sentinel text is also absent from the isolated
profile files. The provider is an explicit synthetic adapter; this receipt
does not establish successful subscription generation.

The corrected reproduction failed all four cases with `running` versus
`cancelled`. After the fix, all **58 checks** in `test_response_close.py`,
`test_generated.py` and `test_provider_errors.py` passed in **88.30 seconds**.
The existing Starlette/httpx deprecation warning remains. This verifies
response closure together with existing generation, scope, replay and public
error behaviour. No helper/model inference, private profile or paid provider
was used.

Receipts in the integration checkout's ignored
`.local/continuation-20261005/`:

- `practice-close-real-before.xml`: four valid reproduction failures.
- `practice-close-verified-after.xml`: 58 passing checks.
- `practice-close-before.xml`: earlier invalid fixture attempt; repository
  lookup preceded router re-registration and therefore failed with `KeyError`.
- `practice-close-after.xml`: an invocation with a nonexistent test filename;
  no tests ran. Neither earlier attempt is counted as regression evidence.

The source/test pair is `runtime/renulus/assessment/generated_streaming.py`
and `tests/assessment/test_response_close.py`. Parent matching installed
cancellation, shutdown/reopen and connected subscription acceptance remain
required under the owner's unsigned current-PC decision.
