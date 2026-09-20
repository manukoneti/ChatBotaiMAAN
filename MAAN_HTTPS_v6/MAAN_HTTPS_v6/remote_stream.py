"""Keep the client connection alive while a slow local vision model loads."""
import json,queue,threading,time
import requests

def stream_remote(url,payload,active,release):
    events=queue.Queue(maxsize=16);stop=threading.Event();holder=[]
    def put(item):
        while not stop.is_set():
            try:events.put(item,timeout=.2);return
            except queue.Full:pass
    def work():
        try:
            with requests.post(url,json=payload,stream=True,timeout=(5,300)) as response:
                holder.append(response);response.raise_for_status()
                for line in response.iter_lines(chunk_size=512):
                    if stop.is_set():break
                    if line:
                        packet=json.loads(line)
                        if packet.get('error'):raise ValueError('Model error')
                        put(packet)
                        if packet.get('done'):return
                if not stop.is_set():put({'error':'Incomplete reply from local model.'})
        except (requests.RequestException,ValueError):
            put({'error':'Local image/translation model failed. Check Ollama and retry with a smaller, clearer image.'})
        finally:
            active.clear()
            release()
    active.set();thread=threading.Thread(target=work,daemon=True);thread.start();began=time.monotonic()
    completed=False
    try:
        while True:
            if time.monotonic()-began>600:raise TimeoutError('Local model exceeded ten minutes.')
            try:packet=events.get(timeout=8)
            except queue.Empty:
                if not active.is_set():raise ValueError('Incomplete local reply.')
                yield {'status':'Reading / translating locally… first use can take several minutes.'};continue
            if packet.get('error'):raise ValueError(packet['error'])
            if packet.get('done_reason')=='length':raise ValueError('Reply reached the length limit. Use a shorter text or crop one section of the photo.')
            delta=packet.get('message',{}).get('content','')
            if delta:yield {'delta':delta}
            if packet.get('done'):
                completed=True
                return
    finally:
        if not completed:
            stop.set()
            if holder:holder[0].close()
            # If still loading, retain the inference slot until the worker exits.
            if not active.is_set():release()
