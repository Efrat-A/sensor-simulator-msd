import logging
from io import BytesIO

import allure
import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@pytest.fixture(autouse=True)
def _capture_sensor_sim_logs(caplog):
    """Capture sensor_sim's debug logs (state transitions, waypoints reached)
    for every test. Pytest shows these under "Captured log call" when a test
    fails -- without this, a failure gives you only the final assertion, not
    the trail of state changes that led to it. Also attached to the Allure
    report (a no-op outside `make test-allure`) so the same trail is visible
    there, pass or fail."""
    caplog.set_level(logging.DEBUG, logger="sensor_sim")
    yield
    if caplog.text:
        allure.attach(caplog.text, name="logs", attachment_type=allure.attachment_type.TEXT)


def attach_figure(fig: plt.Figure, name: str) -> None:
    """Attach a matplotlib figure to the Allure report as a PNG and close it.

    A no-op unless pytest is run with --alluredir (e.g. via `make
    test-allure`), so it costs nothing in a normal test run.
    """
    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    allure.attach(buf.read(), name=name, attachment_type=allure.attachment_type.PNG)
    plt.close(fig)
