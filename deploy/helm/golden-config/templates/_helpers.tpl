{{- define "gc.name" -}}golden-config{{- end -}}

{{- define "gc.labels" -}}
app.kubernetes.io/name: {{ include "gc.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "gc.backendImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.backend }}:{{ .Values.image.tag }}
{{- end -}}

{{- define "gc.frontendImage" -}}
{{ .Values.image.registry }}/{{ .Values.image.frontend }}:{{ .Values.image.tag }}
{{- end -}}
