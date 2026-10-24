"""Run the minimal pipeline without opening a browser. Default uses a labelled demo."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from franny.analysis import rank_notes, analyze
from franny.data import parse_csv, Store
from franny.service import create_and_save
from franny.errors import explain_error


def main():
    parser=argparse.ArgumentParser(description='Import authorized CSV → analyze → generate → save. --live may incur official API charges.')
    parser.add_argument('--csv',default='examples/notes.csv')
    parser.add_argument('--db',default='work/smoke.db')
    parser.add_argument('--provider',choices=['deepseek','qwen','openai','ollama'],default=None)
    parser.add_argument('--live',action='store_true',help='Call configured model exactly once; default is a clearly labelled offline fixture')
    args=parser.parse_args()
    load_dotenv()
    from franny.settings import setting
    provider=args.provider or setting('LLM_PROVIDER','deepseek')
    try:
        notes=parse_csv(Path(args.csv).read_bytes())
        store=Store(args.db)
        n=store.import_notes(notes)
        insights=analyze(rank_notes(store.notes()).head(20))
        draft_id,payload=create_and_save(store,'减脂人，别再和意志力硬刚了','普通健康成年人',insights,provider=provider,demo=not args.live,text_only=True)
        print(json.dumps({'imported':n,'analyzed':insights['sample_size'],'draft_id':draft_id,'mode':payload['mode'],'library_count':len(store.drafts()),'database':args.db},ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps(explain_error(exc,provider),ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
