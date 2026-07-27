<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="cns-contour-rules">
      <rule key="primary" label="Primary" symbol="0" filter="&quot;contclass&quot; = 'primary'"/>
      <rule key="intermediate" label="Intermediate" symbol="1" filter="ELSE"/>
    </rules>
    <symbols>
      <symbol name="0" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="0,115,130,255" type="QString"/><Option name="line_width" value="0.65" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="54,163,174,255" type="QString"/><Option name="line_width" value="0.30" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
