<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ofs-contour-rules">
      <rule key="c0" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/><rule key="c1" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/><rule key="c2" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/><rule key="c3" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/><rule key="c4" label="Balked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'balked_landing'"/>
    </rules>
    <symbols>
      <symbol name="0" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="174,68,45,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="190,103,36,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="170,132,37,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="148,49,92,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="137,41,29,255" type="QString"/><Option name="line_width" value="0.45" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="111,57,40,255" type="QString"/><Option name="line_style" value="dash" type="QString"/><Option name="line_width" value="0.55" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
