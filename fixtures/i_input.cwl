# Fixture I/J: the fault is in a workflow input file, labelled GeoTIFF by the job, not by a tool.
# Vanilla cwltool runs consume. The runner stops at consume's input check, so consume never runs:
# I1 (roads.geojson) in basic mode, I2 (GeoJSON content named .tif) and J (truncated GeoTIFF) only in full.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  raster: {type: File, format: eo:GeoTIFF}
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  consume: {run: tools/consume_geotiff.cwl, in: {data: raster}, out: [size]}
