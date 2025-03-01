# Results

Prefect allows data to be represented by a first-class Prefect object called a `Result`. The Prefect pipeline uses result objects to pass data between Tasks as a first class operation. Users may also use Prefect's result objects to write or read any arbitrary data in their task with a single abstraction.

At a high level, all `State` objects produced by the Prefect pipeline have a `Result` object associated with them. That `Result` object may be a subclass specifying a storage backend, such as `S3Result` or `GCSResult`, which specifies how the outputs of that Task should be handled if they need to be persisted for any reason.

Prefect's result framework was designed with security and privacy concerns in mind. Consequently, Prefect's abstractions allow users to take advantage of all its features without ever needing to surrender control, access, or even visibility of their private data.

[[toc]]

## `Result` objects

A Prefect `Result` object represents data Prefect knows about, most importantly the output of a Prefect Task: anytime a Task runs, its output is encapsulated in a `Result` object. This object retains information about what the data is and how to write or read it if it needs to be saved / retrieved at a later time.

In the unconfigured case, all `State` objects produced by a flow have a basic `Result` object with only `Result.value` set. These base objects do not know how to write themselves to persistent storage.

```python
# access the underlying Result instance
>>> type(state._result)
prefect.engine.result.Result

# this is the type of your Task's return value
>>> type(state._result.value)
dict

# the value can be conveniently accessed via `state.result`
>>> type(state.result)
dict
```

You can instead configure your task to use a subclass of `Result` that aligns with a persistent storage backend. This allows you to turn on persistent forms of caching and checkpointing. (Learn more about that in [Caching and Persisting Data](persistence.md)). These subclasses of `Result` always have four important attributes / methods:

- `location`: the location the data should be stored to (note that this can be templated as [described below](#templating-result-locations))
- `read()`: how to read from the storage backend
- `write()`: how to write to the storage backend
- `exists()`: how to determine if the data exists at the provided location for this storage backend

There are many different `Result` classes aligning with different storage backends depending on your needs, such as `GCSResult` and `S3Result`. See the whole list in the [API docs for results](../../api/latest/engine/results.md).

In addition, you can specify a `Serializer` that transforms Python objects into bytes prior to being written to storage by a `Result`. The same `Serializer` will be used to recover the object from bytes later.

::: tip NoResult vs. a None Result
To distinguish between a Task that runs but does not return output from a Task that has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data. This is in contrast to a `Result` whose value is `None`.
:::

### Interacting with task `Result` objects

The most common scenario in which a user might need to directly interact with a `Result` object produced by the Prefect pipeline in memory is when running flows locally. All Prefect `States` have `Result` objects built into them, which can be accessed via the private `_result` attribute. For convenience, the public `.result` property retrieves the underlying `Result`'s value.

```python
>>> task_ref = flow.get_tasks()[0]
>>> state = flow.run()
>>> state._result.value  # a Flow State's Result value is its Tasks' States
{<Task: add>: <Success: "Task run succeeded.">,
 <Task: add>: <Success: "Task run succeeded.">}
>>> state.result  # the public property aliases the same API as above
{<Task: add>: <Success: "Task run succeeded.">,
 <Task: add>: <Success: "Task run succeeded.">}
>>> state.result[task_ref]._result  # a Task State's Result contains the Task's return value
<Result: 1>
```

## Persisting `Result` objects

Subclasses of `Result` that align with a storage backend have a specific implementation of a `read` / `write` / `exists` interface for persisting its data. These can be used directly by a user to read, write, or check on arbitrary data in storage backends matching the result subclass. They are also used by the Prefect pipeline whenever checkpointing is turned on if it needs to retrieve results from persistent storage.

Each of these methods depend on the `Result.location` attribute to determine where the data should actually be persisted. This `location` attribute is the only value serialized to the database of Prefect Core's server or Prefect Cloud. By default this location is autogenerated by a result's `default_location` method, but it can be provided as a formattable string by the user to configure exactly where the result is located as [described below](#templating-result-locations).

### Persisting user-created `Result` objects

If you want to use the `Result` API yourself, such as in a task, instantiate a configured result object and use its `read`, `write`, and `exists` methods directly however you want to in your task.

For example, if your task needs to read a file from an S3 bucket, consider using Prefect's `S3Result` to identify the S3 file and interact with it:

```python
from prefect import Flow, task
from prefect.engine.results import S3Result

@task
def my_task():
    s3_result = S3Result(bucket='bucket_of_models')
    my_saved_model_result = s3_result.read(location='model.pickle')
    my_model = my_saved_model_result.value
    # ...
```

### Pipeline-persisted `Result` objects

If checkpointing is turned on, the Prefect pipeline will persist the return value of tasks using the `write` method of the task's configured `Result` subclass. Consider the following example task configured to store its return value as a `LocalResult` into the `~/Desktop/HelloWorld/results` directory.

::: tip Enabling Checkpointing During Local Testing
Checkpointing is only turned on by default when running on Prefect Cloud or Server. To enable checkpointing for local testing, set the `PREFECT__FLOWS__CHECKPOINTING` environment variable to `true`.
:::

```python
from prefect import Flow, task
from prefect.engine.results import LocalResult

@task(result=LocalResult(dir='~/Desktop/HelloWorld/results'))
def my_task():
    return 3
```

The `State` object returned from a flow run with this task will have tasks' `Result.value` equal to `3` - the actual return value of the Task. The `Result.location` is the string for the local file path.

```python
>>> state.result[first_result]._result.value
3
>>> state.result[first_result]._result.location
'/Users/prefect/Desktop/HelloWorld/results/prefect-result-2020-02-23t18-38-40-381223-00-00'
```

Inside that file is a `cloudpickle` of the value `3`, as the implementation of `LocalResult` persists the data from `Result.value` as a pickle at the local filesystem location of `Result.location`.

```python
>>> f = open(state.result[first_result]._result.location, 'rb')
>>> content = f.read()
>>> content
b'\x80\x05K\x03.'
>>> import cloudpickle
>>> cloudpickle.loads(content)
3
```

One special result subclass is the `PrefectResult`, which stores the data in a Prefect state database, either Prefect Core's server or Prefect Cloud. You might consider this storage backend since it requires no extra configuration as long as you have tasks which return small pieces of JSON-serializable data. How this actually works is that both the `PrefectResult.value` and `PrefectResult.location` match, so that the `PrefectResult.location` serialized to the state database actually is the JSON representation of the value of the result itself.

To showcase this, below is the same example with a flow configured to checkpoint each task's output using the `PrefectResult`. Note that now both `Result.value` and `Result.location` contain references to the return value of its task, the integer `3`, and it's JSON representation, respectively.

```python
>>> state.result[first_result]._result.value
3
>>> state.result[first_result]._result.location
'3'
```

::: warning Handle your data carefully
Using checkpointing with results means that data will be persisted beyond the Prefect's Python process to a storage location, so it is worth taking some extra time to consider what data is safe to persist where.

In particular, when running on Prefect Cloud, the `location` attribute of the result is what is stored in the state database. When using `PrefectResult` or a custom result subclass, pay special attention to what data is in the `location` attribute.
:::

## How to configure task result persistence

### Choose a `Result` type

`Results` tell Prefect how to interact with storage backends, like a local filesystem or cloud storage.

Configuring a task to persist results requires two steps. First, enable checkpointing. Once this configuration is set, there is a hierarchy to determining what `Result` subclass to use for a given piece of data:

1. You can specify a Flow-level result at Flow-initialization using the `result` keyword argument. If you never specify another result, this is the one that will be used for all your tasks in this particular Flow.
1. Alternatively, you can set a Task-level result. This is achieved using the `result` keyword argument at Task initialization (or in the `@task` decorator). If you provide a result here, it will _always_ be used if the _output_ of this Task needs to be cached for any reason whatsoever.

::: tip The Hierarchy
Task-level results will _always_ be used over flow-level results. Neither will be used if a task's `checkpoint` kwarg is set to `False`, or the global `prefect.config.tasks.checkpointing` value is set to `False`.
:::

::: warning `Results` are always attached to their task's outputs
For example, suppose task A is configured to use result A, and task B to use result B, and that A passes data downstream to B. If B fails and requests a retry, it needs to cache its inputs, one of which came from A. If you are using Cloud, [Cloud will use results to persist the input cache](https://docs.prefect.io/orchestration/faq/dataflow.html#when-is-data-persisted), and since the data is from task A it will use the result configured on A.
:::

::: warning Parameters are different
There is one exception to the rule for Results: Prefect Parameters. Prefect Parameters always use the `PrefectResult` so that their cached values are inspectable in the UI.
:::

### Choose a `Serializer`

A `Serializer` tells Prefect how to transform Python objects into bytes and recover them later. The default implementation (`PickleSerializer`) uses `cloudpickle`, but you can write your own by adopting this template:

```python
class MySerializer(prefect.engine.serializers.Serializer):

    def serialize(self, value: Any) -> bytes:
        # transform a Python object into bytes
        pass

    def deserialize(self, value: bytes) -> Any:
        # recover a Python object from bytes
        pass
```

Once created, `Serializers` can be passed directly to `Results`:

```python
Result(serializer=MySerializer())
```

### Templating `Result` locations

By default, Prefect will store task results in a file / directory structure based on the timestamp of when the result is written along with a randomly generated UUID. This of course can be configured to your needs:

- you can provide an explicit, hardcoded filepath using the `location` kwarg on all Result classes
- alternatively, you can provide a `location` [template which will be populated at runtime](/core/concepts/templating.html)

Note that if you pursue option two above, Python string templating allows for powerful configuration. For example, the code below writes task results to both a hardcoded location as well as a location based on the day of the week:

```python
from prefect import task, Flow
from prefect.engine.results import LocalResult


@task(result=LocalResult(location="initial_data.prefect"))
def root_task():
    return [1, 2, 3]

@task(result=LocalResult(location="{date:%A}/{task_name}.prefect"))
def downstream_task(x):
    return [i * 10 for i in x]

with Flow("local-results") as flow:
    downstream_task(root_task)
```

To learn more about using results, check out the tutorial on [Using Results](../advanced_tutorials/using-results.html). If you used to use Result Handlers prior to 0.11.0, that tutorial also has a section on [Migrating from Result Handlers](../advanced_tutorials/using-results.html#migrating-from-result-handlers)
