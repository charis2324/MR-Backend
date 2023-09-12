def get_duration_estimation(
    durations: list,
    task_queue_length: int,
    is_busy: bool,
    period=5,
    default_duration=10,
):
    print(f"durations: {durations}")
    print(f"task_queue_length: {task_queue_length}")
    print(f"is_busy: {is_busy}")
    if not durations:  # if durations list is empty
        duration = default_duration
    elif len(durations) < period:  # if there are less than 'period' durations
        duration = sum(durations) / len(durations)
    else:  # if there are 'period' or more durations
        duration = sum(durations[-period:]) / period
    n_tasks = task_queue_length + 2 if is_busy.is_set() else task_queue_length + 1
    print(f"duration: {duration}")
    print(f"n_tasks: {n_tasks}")
    return duration * n_tasks
