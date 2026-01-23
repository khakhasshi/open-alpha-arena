import React from 'react'

export default function Footer() {
  return (
    <footer className="w-full py-2 px-4 border-t bg-background/50 text-center text-[10px] text-muted-foreground">
      <div className="flex flex-col items-center justify-center gap-1">
        <p>Copyright © 2021-2025 湖南节点数智网络科技有限责任公司版权所有</p>
        <div className="flex gap-4">
          <span>网站备案：湘ICP备18015824号-1</span>
        </div>
        <p className="opacity-70">仅为大模型技术验证，所有操作不构成投资建议</p>
      </div>
    </footer>
  )
}
