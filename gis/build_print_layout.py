"""Build the "Station punctuality" print layout and export it as PNG.

Run from the QGIS Python console with station_punctuality.qgz open:

    exec(open("gis/build_print_layout.py", encoding="utf-8").read())

The layout contains a map of Switzerland and an inset of Neuchatel /
La Chaux-de-Fonds on the SITN orthophoto. The print basemap is the swisstopo
grey national map served as WMS: unlike the WMTS used on screen, the WMS
renders the map scale that fits the export resolution. The image is written to
docs/station_punctuality_map.png next to the project folder.
"""

import os
from datetime import date

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLegendStyle,
    QgsMapLayerLegendUtils,
    QgsProperty,
    QgsRasterLayer,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemMapOverview,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsTextFormat,
)
from qgis.PyQt.QtGui import QColor, QFont

LAYOUT_NAME = "Station punctuality"
TITLE = "Share of late departures by station"
SOURCE = (
    "Data: transport.opendata.ch, Oracle hub · Basemaps: © swisstopo, SITN · "
    "Delay measured at departure"
)
SWITZERLAND = QgsRectangle(2480000, 1072000, 2840000, 1300000)
NEUCHATEL = QgsRectangle(2546000, 1199500, 2569000, 1222500)
DPI = 200

project = QgsProject.instance()
stations = project.mapLayersByName("station_punctuality")[0]


def wms_layer(name, url, layer):
    """Return the project layer called name, adding it (hidden) if missing."""
    found = project.mapLayersByName(name)
    if found:
        return found[0]
    source = (
        f"contextualWMSLegend=0&crs=EPSG:2056&dpiMode=7&format=image/png"
        f"&layers={layer}&styles&url={url}"
    )
    added = QgsRasterLayer(source, name, "wms")
    project.addMapLayer(added, False)
    project.layerTreeRoot().addLayer(added).setItemVisibilityChecked(False)
    return added


sitn = wms_layer("SITN orthophoto (WMS)", "https://sitn.ne.ch/ogc-sitn-open/wms", "orthophoto2016")
swisstopo = wms_layer(
    "swisstopo national map grey (WMS)", "https://wms.geo.admin.ch/", "ch.swisstopo.pixelkarte-grau"
)

def _as_date(value):
    text = value.toString("yyyy-MM-dd") if hasattr(value, "toString") else str(value)
    return date.fromisoformat(text[:10])


feature = next(stations.getFeatures())
start, end = _as_date(feature["period_start"]), _as_date(feature["period_end"])
period = f"{start.day} {start:%b} – {end.day} {end:%b %Y}"


def text(layout, content, x, y, w, h, size, bold=False, color="#1f1f1f"):
    item = QgsLayoutItemLabel(layout)
    item.setText(content)
    fmt = QgsTextFormat()
    font = QFont("Open Sans")
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSize(size)
    fmt.setColor(QColor(color))
    item.setTextFormat(fmt)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(w, h))
    return item


def map_item(layout, layers, extent, x, y, w, h):
    item = QgsLayoutItemMap(layout)
    item.setRect(0, 0, w, h)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(w, h))
    item.setLayers(layers)
    item.setKeepLayerSet(True)
    item.zoomToExtent(extent)
    item.setFrameEnabled(True)
    return item


manager = project.layoutManager()
existing = manager.layoutByName(LAYOUT_NAME)
if existing:
    manager.removeLayout(existing)

layout = QgsPrintLayout(project)
layout.initializeDefaults()  # A4 landscape, 297 x 210 mm
layout.setName(LAYOUT_NAME)
manager.addLayout(layout)

text(layout, TITLE, 10, 8, 200, 10, 18, bold=True)
text(
    layout,
    f"{period} · 16 main stations · departed trains with real-time data",
    10, 18, 200, 7, 10, color="#555555",
)

main = map_item(layout, [stations, swisstopo], SWITZERLAND, 10, 28, 200, 150)
inset = map_item(layout, [stations, sitn, swisstopo], NEUCHATEL, 217, 28, 70, 70)

overview = QgsLayoutItemMapOverview("Inset extent", main)
main.overviews().addOverview(overview)
overview.setLinkedMap(inset)
overview.setFrameSymbol(
    QgsFillSymbol.createSimple(
        {"color": "0,0,0,0", "outline_color": "20,20,20", "outline_width": "0.5"}
    )
)

text(layout, "Neuchâtel – La Chaux-de-Fonds\nBasemap: SITN orthophoto", 217, 99, 70, 10, 8, color="#555555")

legend = QgsLayoutItemLegend(layout)
legend.setTitle("Late departures")
legend.setLinkedMap(main)
legend.setAutoUpdateModel(False)
root = legend.model().rootGroup()
root.removeAllChildren()
node = root.addLayer(stations)
node.setCustomProperty("legend/title-label", "Share of departed trains")
# The point size is data-defined (departures), which has no value in a legend:
# draw each class with a fixed size instead.
for index, category in enumerate(stations.renderer().ranges()):
    symbol = category.symbol().clone()
    symbol.setDataDefinedSize(QgsProperty())
    symbol.setSize(3.5)
    QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(node, index, symbol)
legend.model().refreshLayerLegend(node)
for style_name, size, bold in (
    (QgsLegendStyle.Title, 11, True),
    (QgsLegendStyle.Subgroup, 9, False),
    (QgsLegendStyle.SymbolLabel, 9, False),
):
    style = legend.rstyle(style_name)
    fmt = style.textFormat()
    font = QFont("Open Sans")
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSize(size)
    style.setTextFormat(fmt)
legend.setBackgroundEnabled(False)
layout.addLayoutItem(legend)
legend.attemptMove(QgsLayoutPoint(217, 113))
legend.adjustBoxSize()

text(layout, "Symbol size: number of departures", 217, 162, 70, 6, 8, color="#555555")

scalebar = QgsLayoutItemScaleBar(layout)
scalebar.setStyle("Single Box")
scalebar.setLinkedMap(main)
scalebar.applyDefaultSize(Qgis.DistanceUnit.Kilometers)
scalebar.setUnitLabel("km")
scalebar.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.Fixed)
scalebar.setUnitsPerSegment(25)
scalebar.setNumberOfSegments(2)
scalebar.setNumberOfSegmentsLeft(0)
scalebar.setHeight(1.5)
fmt = scalebar.textFormat()
fmt.setFont(QFont("Open Sans"))
fmt.setSize(8)
scalebar.setTextFormat(fmt)
layout.addLayoutItem(scalebar)
scalebar.update()
scalebar.attemptMove(QgsLayoutPoint(10, 181))

north = QgsLayoutItemPicture(layout)
north.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
layout.addLayoutItem(north)
north.attemptMove(QgsLayoutPoint(197, 31))
north.attemptResize(QgsLayoutSize(10, 12))
north.setLinkedMap(main)

text(layout, SOURCE, 10, 194, 277, 6, 7.5, color="#555555")

output = os.path.normpath(os.path.join(project.homePath(), "..", "docs", "station_punctuality_map.png"))
os.makedirs(os.path.dirname(output), exist_ok=True)
settings = QgsLayoutExporter.ImageExportSettings()
settings.dpi = DPI
result = QgsLayoutExporter(layout).exportToImage(output, settings)
print("Export", "OK" if result == QgsLayoutExporter.Success else f"failed ({result})", output)

project.write()
