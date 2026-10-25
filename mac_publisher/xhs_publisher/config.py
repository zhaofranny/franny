"""Only DOM selectors are configurable; website hosts are fixed."""
DEFAULTS={
 'account':['.user-name','.user-info .name','.account-name','.username','.header-user .name'],
 'title':['input[placeholder*="标题"]','div.d-input input'],
 'body':['.tiptap[contenteditable="true"]','.ql-editor[contenteditable="true"]','[contenteditable="true"][role="textbox"]'],
 'upload':['input[type="file"][accept*="image"]','input[type="file"]'],
 'previews':['.img-preview-area .pr','.image-list .image-item','.upload-image-item'],
 'publish':['.publish-page-publish-btn button'],
 'cards':['.note-list .note-item','.note-card','[data-note-id]'],
 'card_title':['.note-title','.title','h3'],
 'card_status':['.note-status','.publish-status','.status'],
 'topic_options':['[role="option"]','.topic-item','.topic-list .topic-item','.mention-item','.topic-suggestion-item'],
 'selected_topics':['.tiptap a[data-type="topic"]','.ql-editor a.topic','.tiptap .topic-tag','.ql-editor .topic-tag'],
 'ai_toggle':['[data-testid="ai-declaration"] input[type="checkbox"]'],
 'original_toggle':['[data-testid="original-declaration"] input[type="checkbox"]'],
}

def load_selectors(root):
 import json
 from pathlib import Path
 path=Path(root)/'selectors.json'
 custom=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
 if set(custom)-set(DEFAULTS): raise ValueError('未知的选择器配置项')
 if any(not isinstance(v,list) or not all(isinstance(x,str) and 0<len(x)<300 for x in v) for v in custom.values()): raise ValueError('选择器配置必须为CSS字符串列表')
 return DEFAULTS|custom
