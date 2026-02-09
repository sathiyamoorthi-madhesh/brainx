import inspect
from app.crud.crud_batch import batch

print("Attributes of batch object:")
print(dir(batch))

if hasattr(batch, 'get_by_teacher'):
    print("\nget_by_teacher exists!")
    try:
        print(inspect.getsource(batch.get_by_teacher))
    except Exception as e:
        print(f"Could not get source: {e}")
else:
    print("\nget_by_teacher DOES NOT exist independently on the object.")
