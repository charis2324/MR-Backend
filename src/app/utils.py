def get_duration_estimation(
    durations, task_queue_length, is_busy, period=5, default_duration=10
):
    if not durations:  # if durations list is empty
        duration = default_duration
    elif len(durations) < period:  # if there are less than 'period' durations
        duration = sum(durations) / len(durations) * task_queue_length
    else:  # if there are 'period' or more durations
        duration = sum(durations[-period:]) / period * task_queue_length
    n_tasks = task_queue_length + 2 if is_busy.is_set() else task_queue_length + 1
    return duration * n_tasks
