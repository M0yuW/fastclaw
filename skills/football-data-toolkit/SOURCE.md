# Source and maintenance

This Skill was initially imported from the FastClaw Go runtime assets at commit
`792417b86b5c12af1b99364865217a74f4d52f38` without copying Git history.

The Python repository owns the competition-aware ESPN and Odds changes through commit
`c3ed452052cb336e5bd133837bfc8f6f258c3dd2`. This Go-specific copy has a distinct Skill
name and adds `thesportsdb_data.py` so the Go Runtime can use the same primary-source-first
policy without changing the historical World Cup Skill.

The copied Skill files retain their original MIT license in `LICENSE`.
