<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="oes-rules">
      <rule key="oes-precision" label="Precision Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'precision_approach'"/>
      <rule key="oes-straight" label="Straight-in Instrument Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'straight_in_instrument_approach'"/>
      <rule key="oes-departure" label="Instrument Departure" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'instrument_departure'"/>
      <rule key="oes-takeoff" label="Take-off Climb" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'take_off_climb'"/>
      <rule key="oes-horizontal" label="Horizontal" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'horizontal'"/>
    </rules>
    <symbols>
      <symbol name="0" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="244,171,160,90" type="QString"/><Option name="outline_color" value="166,83,75,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="245,209,184,96" type="QString"/><Option name="outline_color" value="154,111,83,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="96,100,114,74" type="QString"/><Option name="outline_color" value="53,56,66,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="195,240,230,90" type="QString"/><Option name="outline_color" value="66,132,117,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="182,216,223,80" type="QString"/><Option name="outline_color" value="75,116,126,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="154,158,170,60" type="QString"/><Option name="outline_color" value="82,86,99,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
