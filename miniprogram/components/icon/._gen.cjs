/**
 * 解码 icon.wxss 中的 base64 SVG，提取内部路径，生成新的 icon 组件三件套
 * 新方案：用 <image src="data:image/svg+xml;base64,..."> 替代不支持的 mask-image
 */
const fs = require('fs');
const path = require('path');

const wxssContent = fs.readFileSync(path.join(__dirname, 'icon.wxss'), 'utf-8');

// 解析所有 .icon-xxx { -webkit-mask-image: url("data:...base64,XXXX") }
const regex = /\.icon-([a-zA-Z0-9-]+(?:\\-[a-zA-Z0-9]+)*)\s*\{\s*-webkit-mask-image:\s*url\("data:image\/svg\+xml;base64,([A-Za-z0-9+/=]+)"\)/g;
const icons = {};
let match;
while ((match = regex.exec(wxssContent)) !== null) {
  let name = match[1].replace(/\\-/g, '-');
  const b64 = match[2];
  const svg = Buffer.from(b64, 'base64').toString('utf-8');
  // 提取 <svg ...>INNER</svg> 中的 INNER
  const innerMatch = svg.match(/<svg[^>]*>([\s\S]*)<\/svg>/);
  if (innerMatch) {
    icons[name] = innerMatch[1];
  }
}

console.log(`提取到 ${Object.keys(icons).length} 个图标`);

// 生成 icon.ts
const iconTs = `/**
 * icon 组件 - 与 Web 端 lucide-react 视觉对齐
 * 通过 <image> 渲染 SVG data URI，颜色动态注入
 *
 * 用法：
 *   <icon name="home" size="48rpx" color="#174d5e" />
 *   <icon name="sparkles" size="32rpx" />  <!-- 颜色继承父级 -->
 *
 * 可用图标名见 ICON_PATHS 映射
 */

// SVG 内部路径（lucide-react 图标，stroke-width=2）
const ICON_PATHS: Record<string, string> = {
${Object.entries(icons).map(([name, inner]) => `  '${name}': '${inner}',`).join('\n')}
};

// SVG 模板：fill=none, stroke=动态颜色, stroke-width=2
function buildSvgSrc(name: string, color: string): string {
  const inner = ICON_PATHS[name];
  if (!inner) return '';
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + inner + '</svg>';
  // 微信小程序 image 支持 base64 data URI
  return 'data:image/svg+xml;base64,' + wx.arrayBufferToBase64(stringToBuffer(svg));
}

function stringToBuffer(str: string): ArrayBuffer {
  const arr: number[] = [];
  for (let i = 0; i < str.length; i++) {
    arr.push(str.charCodeAt(i));
  }
  return new Uint8Array(arr).buffer as ArrayBuffer;
}

Component({
  properties: {
    name: {
      type: String,
      value: '',
    },
    size: {
      type: String,
      value: '48rpx',
    },
    color: {
      type: String,
      value: '#6a7d81',
    },
  },
  data: {
    src: '',
  },
  observers: {
    'name, color': function (name: string, color: string) {
      this.setData({ src: buildSvgSrc(name, color) });
    },
  },
  lifetimes: {
    attached() {
      this.setData({ src: buildSvgSrc(this.data.name, this.data.color) });
    },
  },
});
`;

// 生成 icon.wxml
const iconWxml = `<image
  class="icon"
  src="{{src}}"
  mode="aspectFit"
  style="width:{{size}};height:{{size}};"
  aria-hidden="true"
/>`;

// 生成 icon.wxss
const iconWxss = `/* ============================================================
 * icon 组件 - 通过 <image> 渲染 SVG data URI
 * 与 Web 端 lucide-react stroke-width=2 视觉对齐
 * ============================================================ */

.icon {
  display: inline-block;
  vertical-align: middle;
}
`;

fs.writeFileSync(path.join(__dirname, 'icon.ts'), iconTs, 'utf-8');
fs.writeFileSync(path.join(__dirname, 'icon.wxml'), iconWxml, 'utf-8');
fs.writeFileSync(path.join(__dirname, 'icon.wxss'), iconWxss, 'utf-8');

console.log('已生成 icon.ts / icon.wxml / icon.wxss');
console.log('图标列表:', Object.keys(icons).join(', '));
