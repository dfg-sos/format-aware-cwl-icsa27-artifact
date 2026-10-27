# OK.4: no format declared -> skipped and counted, never sent to the service.
cwlVersion: v1.2
class: CommandLineTool
baseCommand: [sh, -c, 'echo hi > plain.txt']
inputs: []
outputs:
  plain: {type: File, outputBinding: {glob: plain.txt}}
