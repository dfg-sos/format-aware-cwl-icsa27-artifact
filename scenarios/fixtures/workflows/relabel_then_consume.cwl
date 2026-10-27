# F3.1/F3.2: a GeoJSON file is labelled GeoTIFF and consumed as GeoTIFF.
# Vanilla cwltool succeeds. F3.1 (name out.geojson) fails in basic mode, F3.2 (out.tif) only in full mode.
cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [https://dfg-sos.github.io/ontologies/eo-formats.owl]
class: Workflow
inputs:
  src: File
  name: string
outputs:
  size: {type: File, outputSource: consume/size}
steps:
  relabel: {run: ../tools/relabel_as_geotiff.cwl, in: {src: src, name: name}, out: [raster]}
  consume: {run: ../tools/consume_geotiff.cwl, in: {data: relabel/raster}, out: [size]}
