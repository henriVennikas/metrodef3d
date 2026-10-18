"""Rebuild the photograph, annotation and auxiliary-mask overview from the manifest."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parent

def main():
    examples = json.loads((ROOT / 'manifest.json').read_text())['examples']
    fig, axes = plt.subplots(len(examples), 3, figsize=(10.5, 3.55 * len(examples)), squeeze=False)
    for row, example in enumerate(examples):
        name = example['image']
        folder = ROOT / name
        for col, filename in enumerate([f'{name}.jpeg', 'annotation_overlay.png', f'{name}_overlay.png']):
            with Image.open(folder / filename) as im:
                axes[row, col].imshow(im)
            axes[row, col].axis('off')
            if row == 0:
                axes[row, col].set_title(['Photograph', 'Annotated reference', 'Auxiliary model mask'][col], fontsize=10)
            if col == 0:
                axes[row, col].text(-.02, .5, name, rotation=90, va='center', ha='right', transform=axes[row, col].transAxes, fontsize=10)
    fig.subplots_adjust(left=.04, right=.995, bottom=.005, top=.97, hspace=.025, wspace=.025)
    fig.savefig(ROOT / 'comparison_figure.pdf', dpi=220)
    plt.close(fig)

if __name__ == '__main__':
    main()
