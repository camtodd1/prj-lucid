<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ofs-rules">
      <rule key="ofs-approach" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/>
      <rule key="ofs-inner-approach" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/>
      <rule key="ofs-transitional" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/>
      <rule key="ofs-inner-transitional" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/>
      <rule key="ofs-balked" label="Baulked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'balked_landing'"/>
    </rules>
    <symbols>
      <symbol name="0" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="79,145,168,76" type="QString"/><Option name="outline_color" value="47,102,122,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="99,165,180,84" type="QString"/><Option name="outline_color" value="57,121,138,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="127,167,176,68" type="QString"/><Option name="outline_color" value="75,118,130,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="108,180,186,72" type="QString"/><Option name="outline_color" value="63,135,144,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="71,123,142,82" type="QString"/><Option name="outline_color" value="36,79,97,255" type="QString"/><Option name="outline_width" value="0.4" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="fill" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" enabled="1"><Option type="Map"><Option name="color" value="156,174,179,60" type="QString"/><Option name="outline_color" value="109,129,136,255" type="QString"/><Option name="outline_width" value="0.3" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/><Option name="style" value="solid" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
