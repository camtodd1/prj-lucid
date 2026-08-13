<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="oes-contour-rules">
      <rule key="c0" label="Precision Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'precision_approach'"/><rule key="c1" label="Straight-in Instrument Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'straight_in_instrument_approach'"/><rule key="c2" label="Instrument Departure" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'instrument_departure'"/><rule key="c3" label="Take-off Climb" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'take_off_climb'"/><rule key="c4" label="Horizontal" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'horizontal'"/>
    </rules>
    <symbols>
      <symbol name="0" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="33,85,117,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="22,105,95,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="56,57,157,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="0,113,138,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="48,72,94,255" type="QString"/><Option name="line_width" value="0.35" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="26,77,101,255" type="QString"/><Option name="line_style" value="dash" type="QString"/><Option name="line_width" value="0.55" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
