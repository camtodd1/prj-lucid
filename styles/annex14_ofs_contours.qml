<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ofs-contour-rules">
      <rule key="c0" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/><rule key="c1" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/><rule key="c2" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/><rule key="c3" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/><rule key="c4" label="Baulked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'balked_landing'"/>
    </rules>
    <symbols>
      <symbol name="0" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="47,102,122,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="57,121,138,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="75,118,130,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="63,135,144,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="36,79,97,255" type="QString"/><Option name="line_width" value="0.45" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="109,129,136,255" type="QString"/><Option name="line_style" value="dash" type="QString"/><Option name="line_width" value="0.55" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
