# demo_aggrid_lazy_updates_WORKING.py
# NiceGUI 3.7.1 – minimal, correct AG Grid update patterns

from __future__ import annotations

import random
import time
from typing import Dict, List

from nicegui import ui, native


def build_rows(n: int = 200) -> List[Dict]:
    rows = []
    now = time.time()
    for i in range(n):
        rows.append({
            'id': i,
            'name': f'file_{i:04d}.tif',
            'status': 'idle',
            'score': round(random.random(), 3),
            'updated_s': now,
        })
    return rows


@ui.page('/')
def home() -> None:
    print('[app] serving /')

    rows = build_rows()
    print(f'[app] built {len(rows)} rows')
    # print(f'[app] rows:')
    # for row in rows:
    #     print(f'  {row}')

    grid = ui.aggrid({
        'columnDefs': [
            {'headerName': 'ID', 'field': 'id', 'width': 90},
            {'headerName': 'Name', 'field': 'name', 'flex': 1},
            {'headerName': 'Status', 'field': 'status'},
            {'headerName': 'Score', 'field': 'score'},
            {'headerName': 'Updated', 'field': 'updated_s'},
        ],
        'rowData': rows,              # ✅ REQUIRED
        'getRowId': {'function': 'params.data.id'},  # ✅ enables transactions
    }).classes('w-full h-[500px]')

    def update_one_random_row() -> None:
        i = random.randrange(len(rows))
        row = rows[i]

        before = dict(row)
        row['score'] = round(random.random(), 3)
        row['updated_s'] = time.time()
        row['status'] = 'running'

        print(f'[one-row] before={before}')
        print(f'[one-row] after ={row}')

        grid.run_grid_method('applyTransaction', {
            'update': [row],
        })

    def update_row_zero() -> None:
        row = rows[0]
        row['score'] = round(random.random(), 3)
        row['updated_s'] = time.time()
        row['status'] = 'done'

        print('[row0] updated')
        grid.run_grid_method('applyTransaction', {
            'update': [row],
        })

    def full_refresh() -> None:
        print('[full] rebuilding ALL rows')
        new_rows = build_rows(len(rows))
        rows[:] = new_rows
        grid.options['rowData'] = rows
        grid.update()

    with ui.row().classes('gap-2 mt-2'):
        ui.button('Update one random row', on_click=update_one_random_row)
        ui.button('Update row 0', on_click=update_row_zero)
        ui.button('Full refresh (slow)', on_click=full_refresh)


port = native.find_open_port()
print(f'[app] starting on port {port}')
ui.run(port=port, reload=False)