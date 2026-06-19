<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ofs-rules">
      <rule key="ofs-approach" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/>
      <rule key="ofs-inner-approach" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/>
      <rule key="ofs-transitional" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/>
      <rule key="ofs-inner-transitional" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/>
      <rule key="ofs-balked" label="Balked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'balked_landing'"/>
      <rule key="ofs-other" label="Other OFS" symbol="5" else="1"/>
    </rules>
    <symbols>
      <symbol name="0" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="231,111,81,76" type="QString"/><Option name="outline_color" value="174,68,45,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="244,162,97,84" type="QString"/><Option name="outline_color" value="190,103,36,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="233,196,106,68" type="QString"/><Option name="outline_color" value="170,132,37,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="213,93,146,72" type="QString"/><Option name="outline_color" value="148,49,92,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="196,69,54,82" type="QString"/><Option name="outline_color" value="137,41,29,255" type="QString"/><Option name="outline_width" value="0.4" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="214,122,85,60" type="QString"/><Option name="outline_color" value="126,72,49,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
