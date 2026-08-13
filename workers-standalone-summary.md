# Workers 单独运行总结

当前后端的 `workers` 是一个可单独启动的后台生成任务执行入口：通过 `make workers` 或 `uv run python -m app.workers.generation_worker` 启动，内部复用 `GenerationQueueService.run_worker_loop()`，按 `QUEUE_WORKER_CONCURRENCY` 构建多槽位 worker 池，基于 PostgreSQL 队列表、心跳、行锁领取、重试和 stale 恢复来异步执行各类生成任务。
