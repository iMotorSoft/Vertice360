# Stub for tracing module
# Future integration with OpenTelemetry would go here.

def get_tracer(name: str):
    """
    Returns a dummy tracer.
    """
    return DummyTracer()

class DummyTracer:
    def start_span(self, name: str):
        return DummySpan()

class DummySpan:
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def set_attribute(self, key, value):
        pass
