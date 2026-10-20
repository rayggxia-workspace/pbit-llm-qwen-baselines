# Issue73 Llama2 task evaluation

2026-10-20, jieruiz. Scope: full PIQA1838/ARC-E2376, 13 cases each, source and numerical kernels inherited from merged PR52/62.

Base 18b887bd2d0cd6c06d070d8dafaf8b979742fdcf; branch task/73-llama2-task-accuracy; directory tmp/llama2-task-accuracy-issue73-20261020. No other member job or worktree modified. Apple PR67 results reused with SHA; no duplicate model download.

Current: local adapter/runner/CPU contracts prepared; AST parse passed. Local Python lacks Torch; numerical CPU tests must run from frozen remote snapshot in CPU Slurm job. GPU preparation and formal workers NOT yet submitted at this point.

Next: freeze commit/archive, stage personal remote project, submit CPU preflight; GPU strict WT2/cache/32-layer/memory gates; only then 26 formal cases via dependent Slurm workers. Capture IDs and immutable source/request/model/config SHA. Never overwrite execution snapshots.

Server model /home/Hongjie_Zeng/pbit_llm/models/Llama-2-7b-hf; identity /home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14/model_identity.json. Existing Issue19 jobs not rerun. New project /home/Hongjie_Zeng/projects/pbit-llama2-task-accuracy-20261020-issue73.

Projects scope unavailable in prior verified API query (read:project missing); board pending. Issue remains open until PR accepted, scores remain pending until sealed.
