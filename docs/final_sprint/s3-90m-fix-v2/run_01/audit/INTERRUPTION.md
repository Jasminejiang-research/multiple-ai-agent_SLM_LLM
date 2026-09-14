# User-confirmed interruption

The user explicitly confirmed manually interrupting this test because Research already took more than 20 minutes.
Original controller result remains `resource_stopped`: after a 2048.078-second observation gap the new guard cancelled the request.
This is not evidence of an unexplained automatic Windows sleep or a new model decode error. System/Execution requests were accepted and released; explicit user power actions remain authoritative.

The body passed (703 output tokens, 196.359 seconds). Grounding never returned a complete response; its output and usage remain unknown.
Server progress counters are not final usage or a complete plan. No structure repair or Critic was invoked.
Real run: 2 requests, 4994 known total tokens plus 85923 retained unknown reservation, 3584.688 seconds including the interruption and cleanup.
The fresh 5400-second allowance has 1815.312 seconds and 34 requests/409083 charged tokens remaining.
All-history cumulative: 18 requests, 387486 charged tokens, 13778.171 seconds. No previous consumption is refunded.

Latest user instruction authorizes simplifying Research and limiting its total generation time to 20 minutes. No full-D restart was authorized by this interruption record.
