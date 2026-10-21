"""Export a trusted original training checkpoint to a tensor-only state dictionary.

Use the matching release config. Does not export optimizer/scheduler/RNG state.
No download, training, pickle fallback or publication is performed.
"""
import argparse,hashlib,json
from pathlib import Path
import torch


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    with torch.serialization.safe_globals([torch.torch_version.TorchVersion]):
        cp=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    state={k:v.detach().cpu().contiguous() for k,v in cp['model_state'].items()}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    torch.save(state,a.output)
    loaded=torch.load(a.output,map_location='cpu',weights_only=True)
    assert loaded.keys()==state.keys() and all(torch.equal(v,loaded[k]) for k,v in state.items())
    print(json.dumps(dict(selected_epoch=cp.get('epoch'),tensor_count=len(state),
        sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),bytes=a.output.stat().st_size,
        note='Use this SHA in the matching config. Serialization bytes can differ; tensor equality is the invariant.'),indent=2))


if __name__=='__main__':main()
