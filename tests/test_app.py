from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_app_import_generate_and_history(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'ui.db'))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
    assert not app.exception
    app.checkbox(key="data_authorized").check().run()
    app.toggle[0].set_value(True).run()
    next(b for b in app.button if b.label == '加载虚构示例').click().run()
    assert not app.exception
    assert app.metric[0].value == '6'
    next(b for b in app.button if b.label == '生成原创草稿').click().run()
    assert not app.exception
    assert 'draft' in app.session_state
    assert len(app.expander) == 1
    next(b for b in app.button if b.label == "生成原创封面和配图 PNG").click().run()
    assert not app.exception
    assert len(app.session_state["card_images"]) == 4
