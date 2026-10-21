"""Build-time machine translation helper; runtime uses only bundled JSON.
Uses Google's public web translation endpoint. No credentials or user content are sent.
Review generated packs before release; administrators can override any entry.
"""
import concurrent.futures,json,re,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]/'app/locales'
LANGUAGES={'fr':'fr','es':'es','de':'de','it':'it','pt-br':'pt','nl':'nl','pl':'pl','ru':'ru','uk':'uk','cs':'cs','sv':'sv','da':'da','nb':'no','fi':'fi','tr':'tr','ar':'ar','he':'iw','ja':'ja','ko':'ko','zh-cn':'zh-CN'}
SOURCE=json.loads((ROOT/'en.json').read_text())
PATTERN=re.compile(r'\$?\{[^{}]+\}|https?://[^\s<>]+|\n|\b(?:Gatearr|Emby|Jellyfin|Seerr|Radarr|Sonarr|Bazarr|SMTP|API|PNG|SVG|Font Awesome|App Store|Play Store|Windows|Android|iPhone|macOS)\b')
def protect(source):
    tokens=[]
    def sub(m):tokens.append(m[0]);return '__PH_'+str(len(tokens)-1)+'__'
    return PATTERN.sub(sub,source),tokens

def batch(client,target,entries,depth=0):
    prepared=[protect(v) for _,v in entries]
    q=prepared[0][0] if len(entries)==1 else '\n'.join('[GA%04d] '%i+p[0] for i,p in enumerate(prepared))
    for attempt in range(3):
        try:
            r=client.get('https://translate.googleapis.com/translate_a/single',params={'client':'gtx','sl':'en','tl':target,'dt':'t','q':q});r.raise_for_status()
            text=''.join(part[0] or '' for part in r.json()[0]);text=('[GA0000] '+text) if len(entries)==1 else text;markers=list(re.finditer(r'\[\s*GA\s*(\d+)\s*\]',text,re.I))
            if [int(m[1]) for m in markers]!=list(range(len(entries))):raise ValueError('Translation markers changed')
            result={}
            for i,((key,source),(_,tokens)) in enumerate(zip(entries,prepared)):
                value=text[markers[i].end():markers[i+1].start() if i+1<len(markers) else len(text)].strip()
                for j,token in enumerate(tokens):
                    pattern=r'__\s*PH\s*_\s*'+str(j)+r'\s*__'
                    if not re.search(pattern,value,re.I):raise ValueError('Translation placeholder changed')
                    value=re.sub(pattern,lambda _:token,value,flags=re.I)
                if not value:raise ValueError('Empty translation')
                if set(re.findall(r'\$?\{[^{}]+\}',source))!=set(re.findall(r'\$?\{[^{}]+\}',value)):raise ValueError('Invalid placeholders')
                result[key]=value
            return result
        except (httpx.HTTPError,ValueError,TypeError,IndexError) as error:
            if attempt==2:
                if len(entries)>1 and depth<8:
                    middle=len(entries)//2;return {**batch(client,target,entries[:middle],depth+1),**batch(client,target,entries[middle:],depth+1)}
                raise RuntimeError(str(error)+' '+target+' '+repr(entries[0][0]))
            time.sleep(1+attempt*2)

def build(item):
    code,target=item;path=ROOT/(code+'.json');values=json.loads(path.read_text()) if path.exists() else {}
    pending=[(k,v) for k,v in SOURCE.items() if k not in values];chunks=[];chunk=[];size=0
    for entry in pending:
        length=len(protect(entry[1])[0])+12
        if chunk and size+length>1800:chunks.append(chunk);chunk=[];size=0
        chunk.append(entry);size+=length
    if chunk:chunks.append(chunk)
    with httpx.Client(timeout=40,follow_redirects=True) as client:
        for i,chunk in enumerate(chunks):
            values.update(batch(client,target,chunk));temp=path.with_suffix('.tmp');temp.write_text(json.dumps({k:values[k] for k in SOURCE if k in values},indent=2,ensure_ascii=False)+'\n');temp.replace(path)
            print(code,i+1,'/',len(chunks),flush=True);time.sleep(.3)
    assert set(SOURCE)<=set(values)
    return code,len(values)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(build,item) for item in LANGUAGES.items()]):
            try:print('DONE',future.result(),flush=True)
            except Exception as error:print('FAILED',error,flush=True)
