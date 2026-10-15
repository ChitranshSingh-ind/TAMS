2026-10-15 17:26:31,920 [CRITICAL] root: Uncaught application exception:
Traceback (most recent call last):
  File "sqlalchemy\engine\base.py", line 1946, in _exec_single_context
  File "sqlalchemy\engine\default.py", line 1192, in do_execute
sqlite3.OperationalError: no such table: batches

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "main.py", line 87, in <module>
  File "main.py", line 80, in main
  File "app\ui\main_window.py", line 93, in __init__
  File "app\ui\main_window.py", line 233, in setup_ui
  File "app\ui\mixins\fees_mixin.py", line 206, in create_fees_page
  File "app\services\batch_service.py", line 84, in get_active_batches
  File "sqlalchemy\orm\session.py", line 2594, in scalars
  File "sqlalchemy\orm\session.py", line 2363, in _execute_internal
  File "sqlalchemy\orm\context.py", line 316, in orm_execute_statement
  File "sqlalchemy\engine\base.py", line 1451, in execute
  File "sqlalchemy\sql\elements.py", line 533, in _execute_on_connection
  File "sqlalchemy\engine\base.py", line 1671, in _execute_clauseelement
  File "sqlalchemy\engine\base.py", line 1825, in _execute_context
  File "sqlalchemy\engine\base.py", line 1965, in _exec_single_context
  File "sqlalchemy\engine\base.py", line 2335, in _handle_dbapi_exception
  File "sqlalchemy\engine\base.py", line 1946, in _exec_single_context
  File "sqlalchemy\engine\default.py", line 1192, in do_execute
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: batches
[SQL: SELECT batches.id, batches.name, batches.start_time, batches.end_time, batches.days, batches.monthly_fee, batches.active, batches.created_at, batches.updated_at 
FROM batches 
WHERE batches.active IS 1 ORDER BY batches.name]
(Background on this error at: https://sqlalche.me/e/21/e3q8)

2026-10-15 17:27:16,424 [CRITICAL] root: Uncaught application exception:
Traceback (most recent call last):
  File "sqlalchemy\engine\base.py", line 1946, in _exec_single_context
  File "sqlalchemy\engine\default.py", line 1192, in do_execute
sqlite3.OperationalError: no such table: batches

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "main.py", line 87, in <module>
  File "main.py", line 80, in main
  File "app\ui\main_window.py", line 93, in __init__
  File "app\ui\main_window.py", line 233, in setup_ui
  File "app\ui\mixins\fees_mixin.py", line 206, in create_fees_page
  File "app\services\batch_service.py", line 84, in get_active_batches
  File "sqlalchemy\orm\session.py", line 2594, in scalars
  File "sqlalchemy\orm\session.py", line 2363, in _execute_internal
  File "sqlalchemy\orm\context.py", line 316, in orm_execute_statement
  File "sqlalchemy\engine\base.py", line 1451, in execute
  File "sqlalchemy\sql\elements.py", line 533, in _execute_on_connection
  File "sqlalchemy\engine\base.py", line 1671, in _execute_clauseelement
  File "sqlalchemy\engine\base.py", line 1825, in _execute_context
  File "sqlalchemy\engine\base.py", line 1965, in _exec_single_context
  File "sqlalchemy\engine\base.py", line 2335, in _handle_dbapi_exception
  File "sqlalchemy\engine\base.py", line 1946, in _exec_single_context
  File "sqlalchemy\engine\default.py", line 1192, in do_execute
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: batches
[SQL: SELECT batches.id, batches.name, batches.start_time, batches.end_time, batches.days, batches.monthly_fee, batches.active, batches.created_at, batches.updated_at 
FROM batches 
WHERE batches.active IS 1 ORDER BY batches.name]
(Background on this error at: https://sqlalche.me/e/21/e3q8)

