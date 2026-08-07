<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="4.0.2-Norrköping" styleCategories="AllStyleCategories" labelsEnabled="0">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ils-bra-surface-rules">
      <rule key="horizontal" label="Horizontal protection area" symbol="0" filter="&quot;surface_role&quot; LIKE '%horizontal%'"/>
      <rule key="longitudinal" label="0.5° longitudinal surface" symbol="1" filter="&quot;surface_role&quot; LIKE '%longitudinal%'"/>
      <rule key="lateral" label="2° lateral surface" symbol="2" filter="&quot;surface_role&quot; LIKE '%lateral%'"/>
    </rules>
    <symbols>
      <symbol name="0" type="fill" alpha="1">
        <layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="77,63,130,42" type="QString"/><Option name="outline_color" value="77,63,130,255" type="QString"/><Option name="outline_style" value="solid" type="QString"/><Option name="outline_width" value="0.60" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="joinstyle" value="round" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer>
      </symbol>
      <symbol name="1" type="fill" alpha="1">
        <layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="109,82,166,32" type="QString"/><Option name="outline_color" value="91,65,148,255" type="QString"/><Option name="outline_style" value="solid" type="QString"/><Option name="outline_width" value="0.52" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="joinstyle" value="round" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer>
      </symbol>
      <symbol name="2" type="fill" alpha="1">
        <layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="75,111,170,26" type="QString"/><Option name="outline_color" value="62,94,150,255" type="QString"/><Option name="outline_style" value="dash" type="QString"/><Option name="outline_width" value="0.48" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="joinstyle" value="round" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
