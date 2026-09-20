Shader "RFThreat/SoftHeatmap"
{
    Properties
    {
        _CoreColor ("Core Color", Color) = (1, 0.82, 0.12, 1)
        _Tint ("Tint", Color) = (1, 0.08, 0.02, 0.55)
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off
        Offset -1, -1

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            fixed4 _Tint;
            fixed4 _CoreColor;

            v2f vert(appdata input)
            {
                v2f output;
                output.vertex = UnityObjectToClipPos(input.vertex);
                output.uv = input.uv;
                return output;
            }

            fixed4 frag(v2f input) : SV_Target
            {
                float2 centered = (input.uv - 0.5) * 2.0;
                float distanceFromCenter = length(centered);
                float softField = 1.0 - smoothstep(0.32, 1.0, distanceFromCenter);
                softField = pow(saturate(softField), 1.35);
                float hotCenter = 1.0 - smoothstep(0.0, 0.34, distanceFromCenter);
                fixed3 heatColor = lerp(_Tint.rgb, _CoreColor.rgb, hotCenter * 0.72);
                return fixed4(heatColor, _Tint.a * softField);
            }
            ENDCG
        }
    }
}
