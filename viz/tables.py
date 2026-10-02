"""Table rendering shared by the pages.

`st.dataframe` draws onto a canvas, so a browser selection cannot pick it up and
it will not paste into a document. `st.table` emits a real HTML table, which
Word and Google Docs both accept as a table when pasted.
"""

import pandas as pd
import streamlit as st


def show_table(
    data,
    *,
    column_config: dict | None = None,
    formats: dict[str, str] | None = None,
    static: bool = False,
) -> None:
    """Render `data`, either as an interactive grid or a pasteable HTML table.

    `formats` maps a column name to a format string such as `"{:+.1f}"`, and is
    only used for the static rendering since `column_config` cannot apply there.
    """
    frame = pd.DataFrame(data)

    if not static:
        st.dataframe(
            frame, hide_index=True, width="stretch", column_config=column_config
        )
        return

    display = frame.copy()
    for column, spec in (formats or {}).items():
        if column in display.columns:
            display[column] = display[column].map(spec.format)

    # The first column becomes the row label, which is how st.table hides the
    # otherwise meaningless numeric index.
    st.table(display.set_index(display.columns[0]))
