_active_model = None
_model_type = None

def _probe_gemini():
    return None

def _load_fallback():
    class Dummy:
        def encode(self, x): return x
    return Dummy()

def _init():
    global _active_model, _model_type
    if _active_model is not None:
        return
    gemini = _probe_gemini()
    if gemini:
        _active_model = gemini
        _model_type = "gemini"
    else:
        _active_model = _load_fallback()
        _model_type = "fallback"

def embed_query(query: str):
    _init()
    if _model_type == "gemini":
        return _active_model.embed_query(query)
    return _active_model.encode([query])

print(embed_query("test"))
