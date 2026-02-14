# demo_aggrid_lazy_updates_v5.py
"""NiceGUI 3.7.1 demo: AG Grid with *lazy* row updates (single-row vs full refresh).

Run:
  uv run python sandbox/lazy-demos/demo_aggrid_lazy_updates_v5.py

Notes:
- We avoid awaiting `grid.run_grid_method('applyTransaction', ...)` because
  that grid API call does not return a value; waiting for a JS response can time out.
- The grid must have an explicit height, otherwise you'll see the overlay
  "no rows to show" even when rowData is present.
"""

from __future__ import annotations

import random
import time
from typing import Dict, List

from nicegui import ui


def _make_rows(n: int = 200) -> List[Dict]:
    rows = []
    now = time.time()
    for i in range(n):
        rows.append({
            'id': i,
            'name': f'file_{i:04d}.tif',
            'status': random.choice(['idle', 'running', 'done', 'error']),
            'score': round(random.random(), 3),
            'updated_s': now,
            'note': '',
        })
    return rows


@ui.page('/')
def home() -> None:
    print('[app] serving /')

    rows = _make_rows()
    print(f'[app] built {len(rows)} rows')

    grid = ui.aggrid({
        'columnDefs': [
            {'headerName': 'ID', 'field': 'id', 'width': 90},
            {'headerName': 'Name', 'field': 'name', 'flex': 1},
            {'headerName': 'Status', 'field': 'status'},
            {'headerName': 'Score', 'field': 'score'},
            {'headerName': 'Updated', 'field': 'updated_s'},
            {'headerName': 'Note', 'field': 'note'},
        ],
        'rowData': rows,
        'getRowId': {'function': 'params.data.id'},
    }).classes('w-full h-[500px]')

    def update_one_random_row() -> None:
        i = random.randrange(len(rows))
        row = rows[i]

        before = dict(row)
        row['score'] = round(random.random(), 3)
        row['updated_s'] = time.time()
        if random.random() < 0.35:
            row['status'] = random.choice(['idle', 'running', 'done', 'error'])

        print(f'[one-row] before={before}')
        print(f'[one-row] after ={row}')

        grid.run_grid_method('applyTransaction', {
            'update': [row],
        })

    def update_row_zero() -> None:
        row = rows[0]
        before = dict(row)
        row['score'] = round(random.random(), 3)
        row['updated_s'] = time.time()
        row['status'] = random.choice(['idle', 'running', 'done', 'error'])
        row['note'] = 'row0'
        after = dict(row)

        print(f'[row0] before: {before}')
        print(f'[row0] after:  {after}')
        grid.run_grid_method('applyTransaction', {
            'update': [row],
        })

    def full_refresh() -> None:
        print('[full] rebuilding ALL rows')
        new_rows = _make_rows(len(rows))
        rows[:] = new_rows
        grid.options['rowData'] = rows
        grid.update()

    with ui.row().classes('gap-2 mt-2'):
        ui.button('Update one random row (transaction)', on_click=update_one_random_row)
        ui.button('Update row 0 (transaction)', on_click=update_row_zero)
        ui.button('Full refresh (replace rowData)', on_click=full_refresh)


def main() -> None:
    ui.run(native=False, reload=False)


if __name__ == '__main__':
    main()
