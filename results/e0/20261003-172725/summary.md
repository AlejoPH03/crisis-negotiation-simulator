# E0 smoke test summary

Flags are a heuristic on the model's own text (canned prefixes excluded). Read the transcripts.

Runs: 40 of 40 planned. Stopped: no. Cost: $1.1592.

## Flag counts per model

| Model | Runs | Flag counts |
| --- | --- | --- |
| claude-haiku-4-5 | 20 | ai_disclosure: 4, criminal_no_threat_language: 9, out_of_character: 20, refusal: 20, truncated: 20 |
| claude-sonnet-4-6 | 20 | criminal_no_threat_language: 12, refusal: 1 |

## All runs (flagged first)

| Flags | Model | Criminal | FBI | Trial | Starts | Status | Outcome | Msgs | Transcript |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_authority | 1 | fbi | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial1.md](claude-haiku-4-5/criminal_calculated__vs__fbi_authority__trial1.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_authority | 2 | criminal | completed | none | 10 | [criminal_calculated__vs__fbi_authority__trial2.md](claude-haiku-4-5/criminal_calculated__vs__fbi_authority__trial2.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_authority | 3 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_authority__trial3.md](claude-haiku-4-5/criminal_calculated__vs__fbi_authority__trial3.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_authority | 4 | criminal | completed | none | 10 | [criminal_calculated__vs__fbi_authority__trial4.md](claude-haiku-4-5/criminal_calculated__vs__fbi_authority__trial4.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_authority | 5 | fbi | completed | criminal_release | 5 | [criminal_calculated__vs__fbi_authority__trial5.md](claude-haiku-4-5/criminal_calculated__vs__fbi_authority__trial5.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_empathy | 1 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial1.md](claude-haiku-4-5/criminal_calculated__vs__fbi_empathy__trial1.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_empathy | 2 | criminal | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial2.md](claude-haiku-4-5/criminal_calculated__vs__fbi_empathy__trial2.md) |
| ai_disclosure, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_empathy | 3 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial3.md](claude-haiku-4-5/criminal_calculated__vs__fbi_empathy__trial3.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_empathy | 4 | criminal | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial4.md](claude-haiku-4-5/criminal_calculated__vs__fbi_empathy__trial4.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_calculated | fbi_empathy | 5 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial5.md](claude-haiku-4-5/criminal_calculated__vs__fbi_empathy__trial5.md) |
| ai_disclosure, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_authority | 1 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial1.md](claude-haiku-4-5/criminal_unstable__vs__fbi_authority__trial1.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_authority | 2 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial2.md](claude-haiku-4-5/criminal_unstable__vs__fbi_authority__trial2.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_authority | 3 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial3.md](claude-haiku-4-5/criminal_unstable__vs__fbi_authority__trial3.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_authority | 4 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial4.md](claude-haiku-4-5/criminal_unstable__vs__fbi_authority__trial4.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_authority | 5 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial5.md](claude-haiku-4-5/criminal_unstable__vs__fbi_authority__trial5.md) |
| out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_empathy | 1 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial1.md](claude-haiku-4-5/criminal_unstable__vs__fbi_empathy__trial1.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_empathy | 2 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial2.md](claude-haiku-4-5/criminal_unstable__vs__fbi_empathy__trial2.md) |
| ai_disclosure, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_empathy | 3 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial3.md](claude-haiku-4-5/criminal_unstable__vs__fbi_empathy__trial3.md) |
| criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_empathy | 4 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial4.md](claude-haiku-4-5/criminal_unstable__vs__fbi_empathy__trial4.md) |
| ai_disclosure, criminal_no_threat_language, out_of_character, refusal, truncated | claude-haiku-4-5 | criminal_unstable | fbi_empathy | 5 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial5.md](claude-haiku-4-5/criminal_unstable__vs__fbi_empathy__trial5.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_authority | 2 | criminal | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial2.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_authority__trial2.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_authority | 3 | fbi | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial3.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_authority__trial3.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_authority | 5 | fbi | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial5.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_authority__trial5.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_empathy | 1 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial1.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_empathy__trial1.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_empathy | 2 | criminal | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial2.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_empathy__trial2.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_empathy | 3 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial3.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_empathy__trial3.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_empathy | 4 | criminal | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_empathy__trial4.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_empathy__trial4.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_calculated | fbi_empathy | 5 | fbi | completed | none | 10 | [criminal_calculated__vs__fbi_empathy__trial5.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_empathy__trial5.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_unstable | fbi_authority | 1 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial1.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_authority__trial1.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_unstable | fbi_authority | 3 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial3.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_authority__trial3.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_unstable | fbi_empathy | 1 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial1.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_empathy__trial1.md) |
| criminal_no_threat_language | claude-sonnet-4-6 | criminal_unstable | fbi_empathy | 2 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial2.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_empathy__trial2.md) |
| refusal | claude-sonnet-4-6 | criminal_unstable | fbi_empathy | 4 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial4.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_empathy__trial4.md) |
| - | claude-sonnet-4-6 | criminal_calculated | fbi_authority | 1 | fbi | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial1.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_authority__trial1.md) |
| - | claude-sonnet-4-6 | criminal_calculated | fbi_authority | 4 | criminal | completed | criminal_release | 10 | [criminal_calculated__vs__fbi_authority__trial4.md](claude-sonnet-4-6/criminal_calculated__vs__fbi_authority__trial4.md) |
| - | claude-sonnet-4-6 | criminal_unstable | fbi_authority | 2 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial2.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_authority__trial2.md) |
| - | claude-sonnet-4-6 | criminal_unstable | fbi_authority | 4 | criminal | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial4.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_authority__trial4.md) |
| - | claude-sonnet-4-6 | criminal_unstable | fbi_authority | 5 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_authority__trial5.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_authority__trial5.md) |
| - | claude-sonnet-4-6 | criminal_unstable | fbi_empathy | 3 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial3.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_empathy__trial3.md) |
| - | claude-sonnet-4-6 | criminal_unstable | fbi_empathy | 5 | fbi | completed | none | 10 | [criminal_unstable__vs__fbi_empathy__trial5.md](claude-sonnet-4-6/criminal_unstable__vs__fbi_empathy__trial5.md) |
